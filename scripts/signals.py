"""투자의견·목표주가·추정치·컨센서스의 변화를 종목별로 쌓고, 급변 구간에 이벤트를 발행한다.

숫자 판정은 전부 코드가 한다 (scripts/estimates.py가 원문에서 뽑은 값 기준).
LLM은 이미 발행된 이벤트에 "리포트가 밝힌 변경 이유"를 한두 문장 붙이는 데만 쓴다
(explain_events, skills/explain-event/SKILL.md).

산출물 (매 실행 전체 재계산, 결정적 출력):
  data/stocks/{종목}.json                 종목별 타임라인·변화 기록
  data/events/{발행일}.json               그날 발생한 이벤트 (reason은 재계산해도 유지)
  data/signals/index.json                종목 목록 + 최신 상태
  data/signals/reports.json              report_id -> 그 리포트가 만든 숫자 변화
  data/signals/industry_revisions.json   산업×주차 리비전 방향(상향/하향 종목 수, 비율)

    python scripts/signals.py                 # 재계산만
    python scripts/signals.py --explain 10    # 재계산 + 이유 없는 이벤트의 리포트 10건 설명
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date as Date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import textstore  # noqa: E402
from scripts.estimates import (  # noqa: E402
    RATING_RANK,
    Observation,
    broker_of,
    build_name_map,
    extract,
    norm_name,
)

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "data" / "reports"
STOCKS_DIR = ROOT / "data" / "stocks"
EVENTS_DIR = ROOT / "data" / "events"
SIGNALS_DIR = ROOT / "data" / "signals"
CONFIG_PATH = ROOT / "config" / "events.json"

RATE_LIMITED = False  # explain_events가 사용량 한도로 멈췄는지

METRIC_LABEL = {"revenue": "매출액", "op": "영업이익", "net": "순이익", "eps": "EPS"}
REVISION_METRICS = ("op", "eps")  # 이벤트 판정에 쓰는 지표 (매출액·순이익은 기록만)
# 변화율을 계산할 최소 기준값. 영업이익 2억원 -> 12억원(+500%) 같은 작은 기저 효과를 거른다.
# 단위: 매출·이익은 십억원(10 = 100억원), EPS는 원.
MIN_BASE = {"revenue": 10.0, "op": 10.0, "net": 10.0, "eps": 100.0}
MAX_SEVERITY = 5.0


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def days_between(a: str, b: str) -> int:
    return (Date.fromisoformat(b) - Date.fromisoformat(a)).days


def iso_week(d: str) -> str:
    y, w, _ = Date.fromisoformat(d).isocalendar()
    return f"{y}-W{w:02d}"


def pct(old: float | None, new: float | None) -> float | None:
    if old is None or new is None or old == 0:
        return None
    return round((new - old) / abs(old) * 100, 1)


def speed30(p: float | None, days: int) -> float | None:
    """30일 환산 변화율. 같은 +20%라도 2주 만인지 6개월 만인지 구분한다."""
    if p is None:
        return None
    return round(p / max(days, 1) * 30, 1)


def fmt_money(v: float | None, metric: str) -> str:
    """표 단위(십억원) 값을 읽기 쉬운 원화로. EPS는 원 단위."""
    if v is None:
        return "-"
    if metric == "eps":
        return f"{v:,.0f}원"
    if abs(v) >= 1000:
        return f"{v / 1000:,.2f}조원"
    return f"{v * 10:,.0f}억원"


def fmt_pct(p: float) -> str:
    return f"{p:+.1f}%"


def stock_id(code: str | None, name: str) -> str:
    return code or norm_name(name)


# ---------- 입력 ----------

def load_reports() -> list[dict]:
    out = []
    for p in sorted(REPORTS_DIR.glob("*/*.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def with_text(reports: list[dict]) -> list[dict]:
    """원문이 필요한 파싱용 사본. 원문은 raw-text 브랜치(textstore)에서 읽는다."""
    return [{**r, "pdf_text": textstore.load_text(r)} for r in reports]


def collect(reports: list[dict]):
    """리포트 전체 -> 종목별 관측·이력표 행·이름·산업."""
    reports = with_text(reports)
    name_map = build_name_map(reports)
    by_id = {r["report_id"]: r for r in reports}
    observations: dict[str, list[Observation]] = defaultdict(list)
    table_rows: dict[str, list[dict]] = defaultdict(list)
    names: dict[str, Counter] = defaultdict(Counter)
    codes: dict[str, str | None] = {}
    industries: dict[str, Counter] = defaultdict(Counter)

    for r in reports:
        obs, tables = extract(r, name_map)  # r에는 load_reports_with_text가 원문을 붙여 둔다
        tags = r.get("industries") or []
        for o in obs:
            sid = stock_id(o.code, o.name)
            observations[sid].append(o)
            names[sid][o.name] += 1
            codes[sid] = o.code
            for t in tags:
                # 주인공 리포트의 산업 태그에 더 큰 가중치
                industries[sid][t] += 3 if o.primary else 1
        for code, name, tbl in tables:
            sid = stock_id(code, name)
            names[sid][name] += 1
            codes.setdefault(sid, code)
            for t in tags:
                industries[sid][t] += 1
            for row in tbl.rows:
                table_rows[sid].append({
                    "date": row.date, "rating": row.rating,
                    "target_price": row.target_price, "note": row.note,
                    "source_report": r["report_id"],
                    "source_date": r.get("published_date") or row.date,
                    "broker": broker_of(r),
                })
    return by_id, observations, table_rows, names, codes, industries


# ---------- 종목 1개 분석 ----------

def dedup_observations(obs: list[Observation]) -> list[Observation]:
    """같은 날 같은 종목 관측은 하나로 (기업 리포트를 데일리가 재수록하는 경우)."""
    best: dict[str, Observation] = {}
    for o in sorted(obs, key=lambda o: (o.date, o.report_id)):
        cur = best.get(o.date)
        rank = (o.primary, o.report_type == "individual", bool(o.estimates), bool(o.target_price))
        if cur is None or rank > (cur.primary, cur.report_type == "individual", bool(cur.estimates), bool(cur.target_price)):
            best[o.date] = o
    return [best[d] for d in sorted(best)]


def rating_timeline(obs: list[Observation], rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """이력표 행 + 리포트 관측을 날짜별로 합친 투자의견·목표주가 타임라인과 메모(담당자 변경 등)."""
    points: dict[str, dict] = {}
    notes: dict[tuple[str, str], dict] = {}
    for row in rows:
        if row["note"]:
            notes[(row["date"], row["note"])] = {"date": row["date"], "note": row["note"]}
            continue
        if row["rating"] is None:
            continue
        p = points.setdefault(row["date"], {
            "date": row["date"], "rating": row["rating"], "target_price": row["target_price"],
            "source": "table", "report_id": None, "tp_status": None,
        })
        # 이력표의 최신 행은 그 표를 실은 리포트 자신의 변경이다 (산업 리포트 등).
        # 발행일과 행 날짜가 가까우면 그 리포트를 변경의 출처로 연결한다.
        if p["report_id"] is None and abs(days_between(row["date"], row["source_date"])) <= 3:
            p["report_id"] = row["source_report"]
    for o in obs:
        if o.rating is None and o.target_price is None:
            continue
        p = points.get(o.date)
        if p is None:
            p = points[o.date] = {"date": o.date, "rating": None, "target_price": None,
                                  "source": "report", "report_id": None, "tp_status": None}
        # 리포트 본문 값이 이력표보다 우선 (이력표는 수정주가 기준일 수 있음)
        p["rating"] = o.rating or p["rating"]
        p["target_price"] = o.target_price if o.target_price is not None else p["target_price"]
        p["report_id"] = o.report_id
        p["tp_status"] = o.tp_status
        p["source"] = "report"
    timeline = [points[d] for d in sorted(points) if points[d]["rating"]]
    return timeline, sorted(notes.values(), key=lambda n: n["date"])


def rating_changes(timeline: list[dict], notes: list[dict] | None = None,
                   prev_hints: dict[str, float] | None = None) -> list[dict]:
    """증권사 한 곳의 타임라인에서 투자의견·목표주가가 바뀐 지점.

    prev_hints: {날짜: 본문이 밝힌 직전 목표주가}. 그 증권사의 이전 기록이 하나도 없을 때
    ("목표주가를 기존 8,000원에서 8,500원으로") 첫 관측부터 변화를 잡는 데 쓴다. 이전 날짜를
    모르므로 경과일·속도는 비워 둔다.
    """
    out = []
    prev = None
    notes = notes or []
    prev_hints = prev_hints or {}
    for p in timeline:
        hint = prev_hints.get(p["date"])
        if prev is None and hint and p["target_price"] and hint != p["target_price"]:
            tp_pct = pct(hint, p["target_price"])
            out.append({
                "date": p["date"], "prev_date": None, "days": None,
                "rating_from": p["rating"], "rating_to": p["rating"],
                "tp_from": hint, "tp_to": p["target_price"],
                "tp_pct": tp_pct, "tp_speed30": None,
                "report_id": p["report_id"], "implied_prev": True,
            })
        if prev is not None:
            tp_from, tp_to = prev["target_price"], p["target_price"]
            tp_pct = pct(tp_from, tp_to) if (tp_from and tp_to and tp_from != tp_to) else None
            rating_moved = p["rating"] != prev["rating"]
            if tp_pct is not None or rating_moved:
                days = days_between(prev["date"], p["date"])
                ch = {
                    "date": p["date"], "prev_date": prev["date"], "days": days,
                    "rating_from": prev["rating"], "rating_to": p["rating"],
                    "tp_from": tp_from, "tp_to": tp_to,
                    "tp_pct": tp_pct, "tp_speed30": speed30(tp_pct, days),
                    "report_id": p["report_id"],
                }
                # 교차 검증: 본문이 "유지"라고 했는데 계산상 바뀌었으면 수정주가 등 표기 차이로 보고 표시만
                if tp_pct is not None and p.get("tp_status") == "유지":
                    ch["mismatch"] = True
                # 그 사이 이력표 메모(1년 경과, 담당자 변경 등)
                between = [n["note"].replace("년 경과", "1년 경과") if n["note"] == "년 경과" else n["note"]
                           for n in notes if prev["date"] < n["date"] <= p["date"]]
                if between:
                    ch["note"] = ", ".join(dict.fromkeys(between))
                out.append(ch)
        prev = p
    return out


def series_changes(obs: list[Observation], attr: str, metrics: tuple[str, ...]) -> list[dict]:
    """연속된 두 관측 사이의 같은 연도·지표 변화 (attr = estimates | consensus)."""
    seq = [o for o in obs if getattr(o, attr)]
    out = []
    for a, b in zip(seq, seq[1:]):
        days = days_between(a.date, b.date)
        for year in sorted(set(getattr(a, attr)) & set(getattr(b, attr))):
            for m in metrics:
                old, new = getattr(a, attr)[year].get(m), getattr(b, attr)[year].get(m)
                if old is None or new is None or old == new:
                    continue
                base = MIN_BASE[m]
                turn = None
                if old <= 0 < new:
                    turn = "흑자전환"
                elif old >= 0 > new:
                    turn = "적자전환"
                if turn and max(abs(old), abs(new)) < base:
                    turn = None
                    p = None
                else:
                    p = None if turn or abs(old) < base else pct(old, new)
                out.append({
                    "date": b.date, "prev_date": a.date, "days": days, "year": year, "metric": m,
                    "from": old, "to": new, "pct": p, "speed30": speed30(p, days), "turn": turn,
                    "report_id": b.report_id, "prev_report_id": a.report_id,
                })
    return out


def gap_vs_consensus(o: Observation) -> dict | None:
    """같은 관측 안에서 증권사 추정치가 컨센서스와 얼마나 다른가 (가장 가까운 추정 연도)."""
    for year in sorted(set(o.estimates) & set(o.consensus)):
        for m in ("op", "net"):
            mine, cons = o.estimates[year].get(m), o.consensus[year].get(m)
            if mine is None or cons is None or cons < MIN_BASE[m]:
                continue
            return {"year": year, "metric": m, "estimate": mine, "consensus": cons,
                    "gap_pct": round((mine / cons - 1) * 100, 1)}
    return None


# ---------- 이벤트 ----------

def event_id(*parts) -> str:
    return ":".join(str(p) for p in parts)


def build_events(sid: str, stock: dict, cfg: dict, window_start: str) -> list[dict]:
    base = {"stock_id": sid, "code": stock["code"], "name": stock["name"], "industry": stock["industry"]}
    events = []

    def add(date, type_, severity, headline, report_id=None, data=None, key=""):
        if date < window_start:
            return
        events.append({
            "id": event_id(date, sid, type_, key),
            "date": date, "type": type_, "severity": round(min(severity, MAX_SEVERITY), 2),
            **base, "report_id": report_id, "headline": headline, "data": data or {},
        })

    # 1) 목표주가·투자의견 (증권사별로 따로 본다)
    tp_moves_by: dict[str, list[dict]] = defaultdict(list)  # 방향 연속성·가속 판정용
    for ch in stock["rating_changes"]:
        rid = ch["report_id"]
        b = ch.get("broker", "")
        tp_moves = tp_moves_by[b]
        if ch["rating_from"] != ch["rating_to"]:
            rf, rt = ch["rating_from"], ch["rating_to"]
            if rf in RATING_RANK and rt in RATING_RANK:
                up = RATING_RANK[rt] > RATING_RANK[rf]
                add(ch["date"], "rating_up" if up else "rating_down", 2.0,
                    f"{b} 투자의견 {rf} → {rt}", rid, ch, key=b)
            elif rf == "NR" and rt != "NR":
                add(ch["date"], "coverage_start", 1.0, f"{b} 커버리지 시작 (NR → {rt})", rid, ch, key=b)
            elif rt == "NR":
                why = f" ({ch['note']})" if ch.get("note") else ""
                add(ch["date"], "coverage_end", 1.0, f"{b} 투자의견 {rf} → NR{why}", rid, ch, key=b)
        p = ch["tp_pct"]
        if p is None or ch.get("mismatch"):
            continue
        direction = 1 if p > 0 else -1
        word = "상향" if p > 0 else "하향"
        if abs(p) >= cfg["tp_jump_pct"]:
            add(ch["date"], "tp_up" if p > 0 else "tp_down", abs(p) / cfg["tp_jump_pct"],
                f"{b} 목표주가 {ch['tp_from']:,.0f}원 → {ch['tp_to']:,.0f}원 ({fmt_pct(p)})", rid, ch, key=b)
        # 연속 같은 방향
        streak = 1
        for prev in reversed(tp_moves):
            if days_between(prev["date"], ch["date"]) > cfg["tp_streak_days"]:
                break
            if (1 if prev["tp_pct"] > 0 else -1) != direction:
                break
            streak += 1
        if streak >= cfg["tp_streak"]:
            add(ch["date"], "tp_streak", streak / cfg["tp_streak"],
                f"{b} 목표주가 {streak}회 연속 {word}", rid, {**ch, "streak": streak}, key=b)
        # 가속: 직전 같은 방향 변화보다 30일 환산 속도가 accel_ratio배 이상
        if tp_moves:
            prev = tp_moves[-1]
            same = (prev["tp_pct"] > 0) == (p > 0)
            if same and abs(p) >= cfg["accel_min_pct"] and prev["tp_speed30"] and ch["tp_speed30"] and \
                    abs(ch["tp_speed30"]) >= cfg["accel_ratio"] * abs(prev["tp_speed30"]):
                add(ch["date"], "tp_accel", abs(ch["tp_speed30"]) / abs(prev["tp_speed30"]) / cfg["accel_ratio"],
                    f"{b} 목표주가 {word} 속도 가속 (30일 환산 {fmt_pct(prev['tp_speed30'])} → {fmt_pct(ch['tp_speed30'])})",
                    rid, {**ch, "prev": prev}, key=b)
        tp_moves.append(ch)

    # 2) 증권사 추정치: 관측 쌍마다 가장 큰 변화 하나만 이벤트로
    def biggest(changes, threshold, prefix, type_up, type_down, type_turn, who):
        by_pair = defaultdict(list)
        for c in changes:
            if c["metric"] in REVISION_METRICS:
                by_pair[(c.get("broker", ""), c["prev_date"], c["date"])].append(c)
        for (b, _, d), cs in sorted(by_pair.items()):
            label = who.replace("{b}", b)
            turns = [c for c in cs if c["turn"]]
            if turns:
                c = turns[0]
                add(d, type_turn, 1.5,
                    f"{label}{c['year']}년 {METRIC_LABEL[c['metric']]} {c['turn']} "
                    f"({fmt_money(c['from'], c['metric'])} → {fmt_money(c['to'], c['metric'])})",
                    c["report_id"], c, key=f"{b}{c['year']}{c['metric']}")
                continue
            c = max(cs, key=lambda c: abs(c["pct"] or 0))
            if c["pct"] is None or abs(c["pct"]) < threshold:
                continue
            add(d, type_up if c["pct"] > 0 else type_down, abs(c["pct"]) / threshold,
                f"{label}{c['year']}년 {METRIC_LABEL[c['metric']]} {fmt_pct(c['pct'])} "
                f"({fmt_money(c['from'], c['metric'])} → {fmt_money(c['to'], c['metric'])})",
                c["report_id"], c, key=f"{b}{c['year']}{c['metric']}")

    biggest(stock["estimate_revisions"], cfg["estimate_revision_pct"], "est",
            "est_up", "est_down", "est_turn", "{b} 추정 ")
    biggest(stock["consensus_changes"], cfg["consensus_shift_pct"], "cons",
            "cons_up", "cons_down", "cons_turn", "시장 컨센서스 ")

    # 3) 컨센서스 대비 괴리 (주인공 리포트만)
    for ob in stock["observations"]:
        g = ob.get("gap")
        if not g or not ob["primary"] or abs(g["gap_pct"]) < cfg["estimate_gap_pct"]:
            continue
        if g["gap_pct"] > 300:  # 4배 넘게 차이 나면 원문 표 오기일 가능성이 커서 이벤트로 내지 않는다
            continue
        label = f"{ob.get('broker', '')} {g['year']}년 {METRIC_LABEL[g['metric']]}".strip()
        if g["estimate"] < 0:
            headline = (f"{label} 추정 적자({fmt_money(g['estimate'], g['metric'])}), "
                        f"컨센서스는 흑자({fmt_money(g['consensus'], g['metric'])})")
        else:
            word = "높음" if g["gap_pct"] > 0 else "낮음"
            headline = f"{label} 추정이 컨센서스보다 {abs(g['gap_pct']):.0f}% {word}"
        add(ob["date"], "gap_above" if g["gap_pct"] > 0 else "gap_below",
            abs(g["gap_pct"]) / cfg["estimate_gap_pct"], headline, ob["report_id"], g, key=ob.get("broker", ""))

    # 4) 여러 증권사를 합친 목표주가 컨센서스: 방향과 속도, 증권사들의 동시 움직임
    for c in stock["tp_consensus_changes"]:
        p, n = c["pct"], c["n"]
        if abs(p) >= cfg["tp_consensus_pct"]:
            word = "상향" if p > 0 else "하향"
            speed = f", 30일 누적 {fmt_pct(c['cum30'])}" if c["cum30"] is not None else ""
            add(c["date"], "tp_cons_up" if p > 0 else "tp_cons_down", abs(p) / cfg["tp_consensus_pct"],
                f"목표주가 컨센서스 {c['from']:,.0f}원 → {c['to']:,.0f}원 ({fmt_pct(p)}, {n}개사{speed})",
                c["report_id"], c)
    for w in stock["broker_waves"]:
        word = "상향" if w["direction"] > 0 else "하향"
        add(w["date"], "wave_up" if w["direction"] > 0 else "wave_down", w["count"] / cfg["wave_min_brokers"],
            f"{cfg['wave_days']}일 사이 증권사 {w['count']}곳이 목표주가 {word} ({', '.join(w['brokers'])})",
            w["report_id"], w)
    return events


def tp_consensus(timeline: list[dict], changes: list[dict], cfg: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """증권사별 최신 목표주가를 합친 컨센서스 시계열과 그 변화, 그리고 '여러 증권사가 같은 방향으로
    움직인' 구간.

    컨센서스 = 유효한(최근 tp_valid_days 이내, NR 아님) 증권사별 최신 목표주가의 평균.
    변화율은 새로 커버를 시작하거나 빠진 증권사 효과를 빼고, 기존 증권사의 목표주가 조정분만으로
    계산한다 (구성 변화가 아니라 눈높이 변화를 보려는 것).
    """
    valid_days = cfg["tp_valid_days"]
    latest: dict[str, dict] = {}
    series, cons_changes = [], []
    by_date: dict[str, list[dict]] = defaultdict(list)
    for p in timeline:
        by_date[p["date"]].append(p)

    def alive(d: str) -> dict[str, float]:
        return {b: v["tp"] for b, v in latest.items()
                if v["tp"] and v["rating"] != "NR" and days_between(v["date"], d) <= valid_days}

    for d in sorted(by_date):
        before = alive(d)
        revised = []
        for p in by_date[d]:
            b = p["broker"]
            old = before.get(b)
            latest[b] = {"tp": p["target_price"], "rating": p["rating"], "date": d}
            if old and p["target_price"] and p["rating"] != "NR" and p["target_price"] != old:
                revised.append((b, old, p["target_price"], p.get("report_id")))
        now = alive(d)
        if not now:
            continue
        mean = sum(now.values()) / len(now)
        series.append({"date": d, "mean": round(mean), "n": len(now),
                       "brokers": {b: now[b] for b in sorted(now)}})
        if revised and len(before) >= 2:
            prev_mean = sum(before.values()) / len(before)
            delta = sum(new - old for _, old, new, _ in revised) / len(before)
            p_rev = round(delta / prev_mean * 100, 1)
            cons_changes.append({
                "date": d, "from": round(prev_mean), "to": round(prev_mean + delta), "pct": p_rev,
                "n": len(before), "brokers": [b for b, *_ in revised],
                "report_id": next((rid for *_, rid in revised if rid), None),
            })
    # 30일 누적 속도
    for c in cons_changes:
        window = [x["pct"] for x in cons_changes if 0 <= days_between(x["date"], c["date"]) < 30]
        c["cum30"] = round(sum(window), 1) if len(window) > 1 else None

    # 증권사 동시 움직임: wave_days 안에 wave_min_brokers곳 이상이 같은 방향, 반대 방향은 없음
    waves = []
    moves = [c for c in changes if c["tp_pct"] is not None and not c.get("mismatch")]
    fired: set[int] = set()
    for c in moves:
        recent = [x for x in moves if 0 <= days_between(x["date"], c["date"]) < cfg["wave_days"]]
        last_dir: dict[str, int] = {}
        for x in sorted(recent, key=lambda x: x["date"]):
            last_dir[x["broker"]] = 1 if x["tp_pct"] > 0 else -1
        for direction in (1, -1):
            same = sorted(b for b, v in last_dir.items() if v == direction)
            other = [b for b, v in last_dir.items() if v != direction]
            if len(same) >= cfg["wave_min_brokers"] and not other and direction not in fired:
                fired.add(direction)
                waves.append({"date": c["date"], "direction": direction, "count": len(same),
                              "brokers": same, "report_id": c.get("report_id")})
            elif len(same) < cfg["wave_min_brokers"]:
                fired.discard(direction)  # 흐름이 끊기면 다음 물결은 새로 알린다
    return series, cons_changes, waves


def industry_revisions(stocks: dict[str, dict], window_start: str) -> dict:
    """산업×주차별로 종목의 리비전 방향을 센다. 종목 하나는 그 주 순방향 하나로만 센다."""
    per = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))  # ind -> week -> sid -> net
    seen = defaultdict(lambda: defaultdict(set))
    for sid, s in stocks.items():
        ind = s["industry"]
        if not ind:
            continue
        for ob in s["observations"]:
            if ob["date"] >= window_start:
                seen[ind][iso_week(ob["date"])].add(sid)
        for ch in s["rating_changes"]:
            if ch["date"] >= window_start and ch["tp_pct"] is not None and not ch.get("mismatch"):
                w = iso_week(ch["date"])
                per[ind][w][sid] += 1 if ch["tp_pct"] > 0 else -1
                seen[ind][w].add(sid)
        for c in s["estimate_revisions"]:
            if c["date"] >= window_start and c["metric"] == "op" and (c["pct"] is not None or c["turn"]):
                w = iso_week(c["date"])
                up = (c["pct"] or 0) > 0 or c["turn"] == "흑자전환"
                per[ind][w][sid] += 1 if up else -1
                seen[ind][w].add(sid)
    out = {}
    for ind in sorted(seen):
        weeks = {}
        for w in sorted(seen[ind]):
            nets = per[ind][w]
            up = sum(1 for v in nets.values() if v > 0)
            down = sum(1 for v in nets.values() if v < 0)
            total = len(seen[ind][w])
            weeks[w] = {"up": up, "down": down, "flat": total - up - down, "stocks": total,
                        "ratio": round((up - down) / total, 2) if total else 0.0}
        out[ind] = weeks
    return out


def industry_events(revisions: dict, cfg: dict) -> list[dict]:
    """산업 리비전 방향이 지난 관측 주와 반대로 뒤집히면 이벤트."""
    events = []
    for ind, weeks in revisions.items():
        prev = None
        for w, v in weeks.items():
            if v["up"] + v["down"] < cfg["industry_min_stocks"] or v["up"] == v["down"]:
                continue
            sign = 1 if v["up"] > v["down"] else -1
            if prev and prev[1] != sign:
                y, n = w.split("-W")
                d = Date.fromisocalendar(int(y), int(n), 5).isoformat()  # 그 주 금요일
                word = "상향" if sign > 0 else "하향"
                events.append({
                    "id": event_id(d, ind, "industry_flip"), "date": d,
                    "type": "industry_up" if sign > 0 else "industry_down", "severity": 1.5,
                    "stock_id": None, "code": None, "name": ind, "industry": ind, "report_id": None,
                    "headline": f"{ind} 리비전 방향 {'하향' if sign > 0 else '상향'} → {word} "
                                f"(상향 {v['up']} · 하향 {v['down']}종목)",
                    "data": {"week": w, "prev_week": prev[0], **v},
                })
            prev = (w, sign)
    return events


# ---------- 실행 ----------

def obs_dict(o: Observation) -> dict:
    d = {
        "date": o.date, "report_id": o.report_id, "title": o.title, "primary": o.primary, "broker": o.broker,
        "rating": o.rating, "rating_status": o.rating_status,
        "target_price": o.target_price, "tp_status": o.tp_status, "price": o.price,
        "upside_pct": pct(o.price, o.target_price) if o.price and o.target_price else None,
        "estimates": o.estimates, "consensus": o.consensus,
        "prev_target_price": o.prev_target_price,
    }
    g = gap_vs_consensus(o)
    if g:
        d["gap"] = g
    return d


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=1) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")


def existing_reasons() -> dict[str, dict]:
    keep = {}
    for p in EVENTS_DIR.glob("*.json"):
        for e in json.loads(p.read_text(encoding="utf-8")):
            if e.get("reason") is not None or e.get("reason_checked"):
                keep[e["id"]] = {k: e[k] for k in ("reason", "reason_checked", "reason_at") if k in e}
    return keep


def build(reports: list[dict] | None = None) -> dict[str, list[dict]]:
    """전체 재계산 후 파일을 쓴다. 반환: 발행일 -> 이벤트 목록."""
    cfg = load_config()
    reports = reports if reports is not None else load_reports()
    if not reports:
        return {}
    window_start = cfg.get("window_start") or min(r["published_date"] for r in reports if r.get("published_date"))
    by_id, observations, table_rows, names, codes, industries = collect(reports)

    stocks: dict[str, dict] = {}
    for sid in sorted(set(observations) | set(table_rows)):
        all_obs = observations.get(sid, [])
        rows = table_rows.get(sid, [])
        brokers = sorted({o.broker for o in all_obs} | {r["broker"] for r in rows})
        timeline, notes, changes, obs = [], [], [], []
        est_revs, cons_revs = [], []
        for b in brokers:
            ob_b = dedup_observations([o for o in all_obs if o.broker == b])
            tl, nt = rating_timeline(ob_b, [r for r in rows if r["broker"] == b])
            hints = {o.date: o.prev_target_price for o in ob_b if o.prev_target_price}
            ch = rating_changes(tl, nt, hints)
            for x in (*tl, *nt, *ch):
                x["broker"] = b
            for kind, dest in (("estimates", est_revs), ("consensus", cons_revs)):
                for x in series_changes(ob_b, kind, ("revenue", "op", "net", "eps")):
                    x["broker"] = b
                    dest.append(x)
            timeline += tl
            notes += nt
            changes += ch
            obs += ob_b
        if not timeline and not obs:
            continue
        order = lambda x: (x["date"], x.get("broker", ""))  # noqa: E731
        timeline.sort(key=order)
        changes.sort(key=order)
        obs.sort(key=lambda o: (o.date, o.broker))
        series, cons_changes, waves = tp_consensus(timeline, changes, cfg)
        stocks[sid] = {
            "id": sid,
            "code": codes.get(sid),
            "name": names[sid].most_common(1)[0][0],
            "industry": industries[sid].most_common(1)[0][0] if industries[sid] else None,
            "brokers": brokers,
            "timeline": timeline,
            "notes": sorted(notes, key=order),
            "observations": [obs_dict(o) for o in obs],
            "rating_changes": changes,
            "estimate_revisions": sorted(est_revs, key=order),
            "consensus_changes": sorted(cons_revs, key=order),
            "tp_consensus": series,
            "tp_consensus_changes": cons_changes,
            "broker_waves": waves,
        }

    events: list[dict] = []
    for sid, s in stocks.items():
        evs = build_events(sid, s, cfg, window_start)
        s["events"] = [e["id"] for e in evs]
        events += evs
    revisions = industry_revisions(stocks, window_start)
    events += industry_events(revisions, cfg)

    # 리포트 제목은 이벤트에 붙여 화면이 원문을 따로 읽지 않게 한다
    for e in events:
        r = by_id.get(e["report_id"]) if e["report_id"] else None
        e["title"] = r["title"] if r else None

    reasons = existing_reasons()
    for e in events:
        e.update(reasons.get(e["id"], {}))

    by_date: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        by_date[e["date"]].append(e)
    for d in by_date:
        by_date[d].sort(key=lambda e: (-e["severity"], e["id"]))

    # ---- 쓰기 ----
    for p in STOCKS_DIR.glob("*.json"):
        if p.stem not in stocks:
            p.unlink()
    for sid, s in stocks.items():
        write_json(STOCKS_DIR / f"{sid}.json", s)
    for p in EVENTS_DIR.glob("*.json"):
        if p.stem not in by_date:
            p.unlink()
    for d, evs in by_date.items():
        write_json(EVENTS_DIR / f"{d}.json", evs)

    index = []
    for sid, s in stocks.items():
        last = s["timeline"][-1] if s["timeline"] else {}
        last_obs = s["observations"][-1] if s["observations"] else {}
        last_tp = next((c for c in reversed(s["rating_changes"])
                        if c["tp_pct"] is not None and not c.get("mismatch")), None)
        cons = s["tp_consensus"][-1] if s["tp_consensus"] else None
        latest_by = {}
        for pt in s["timeline"]:
            latest_by[pt["broker"]] = {"rating": pt["rating"], "target_price": pt["target_price"], "date": pt["date"]}
        index.append({
            "id": sid, "code": s["code"], "name": s["name"], "industry": s["industry"],
            "rating": last.get("rating"), "target_price": last.get("target_price"),
            "rating_date": last.get("date"), "rating_broker": last.get("broker"),
            "consensus_tp": cons["mean"] if cons else None, "consensus_n": cons["n"] if cons else 0,
            "brokers": latest_by,
            "price": last_obs.get("price"), "price_date": last_obs.get("date"),
            "last_tp_change": ({"date": last_tp["date"], "pct": last_tp["tp_pct"], "broker": last_tp["broker"]}
                               if last_tp else None),
            "events": len(s["events"]),
            "last_event_date": max((e.split(":")[0] for e in s["events"]), default=None),
            "reports": len({o["report_id"] for o in s["observations"]}),
        })
    write_json(SIGNALS_DIR / "index.json", {"window_start": window_start, "stocks": index})

    report_map: dict[str, list[dict]] = defaultdict(list)
    for sid, s in stocks.items():
        changes = {c["report_id"]: c for c in s["rating_changes"] if c["report_id"]}
        for ob in s["observations"]:
            rid = ob["report_id"]
            ch = changes.get(rid)
            revs = [c for c in s["estimate_revisions"] if c["report_id"] == rid and c["metric"] in REVISION_METRICS]
            report_map[rid].append({
                "stock_id": sid, "name": s["name"], "code": s["code"], "primary": ob["primary"], "broker": ob["broker"],
                "rating": ob["rating"], "rating_status": ob["rating_status"],
                "target_price": ob["target_price"], "price": ob["price"], "upside_pct": ob["upside_pct"],
                "rating_change": ({k: ch[k] for k in ("rating_from", "rating_to", "tp_from", "tp_to", "tp_pct", "prev_date")}
                                  if ch and not ch.get("mismatch") else None),
                "estimate_revisions": revs,
                "gap": ob.get("gap"),
            })
        # 산업 리포트처럼 이력표로만 변경이 확인된 경우
        seen_rids = {o["report_id"] for o in s["observations"]}
        for rid, ch in changes.items():
            if rid in seen_rids or ch.get("mismatch"):
                continue
            report_map[rid].append({
                "stock_id": sid, "name": s["name"], "code": s["code"], "primary": False, "broker": ch["broker"],
                "rating": ch["rating_to"], "rating_status": None,
                "target_price": ch["tp_to"], "price": None, "upside_pct": None,
                "rating_change": {k: ch[k] for k in ("rating_from", "rating_to", "tp_from", "tp_to", "tp_pct", "prev_date")},
                "estimate_revisions": [], "gap": None,
            })
    write_json(SIGNALS_DIR / "reports.json", dict(sorted(report_map.items())))
    write_json(SIGNALS_DIR / "industry_revisions.json", revisions)
    print(f"[signals] 종목 {len(stocks)}, 이벤트 {len(events)} ({len(by_date)}일), 기준 시작일 {window_start}", flush=True)
    return dict(by_date)


# ---------- 변경 이유 (LLM) ----------

_REASON_KEYWORDS = ("목표주가", "추정", "상향", "하향", "조정", "투자의견", "컨센서스", "하회", "상회", "가정")


def reason_excerpt(text: str, limit: int = 6000) -> str:
    """원문 앞부분(요약 박스) + 변경 이유가 나올 만한 문단만 추린다."""
    head = text[:2500]
    paras = [p.strip() for p in text[2500:].split("\n \n") if p.strip()]
    picked = [p for p in paras if any(k in p for k in _REASON_KEYWORDS) and "Compliance" not in p
              and "투자의견 변동 내역" not in p]
    body = "\n\n".join(picked)
    return (head + "\n\n" + body)[:limit]


def explain_events(max_reports: int) -> tuple[int, bool]:
    """이유가 비어 있는 이벤트를 리포트별로 묶어 LLM에 묻는다. 반환: (처리 리포트 수, 중단 여부)."""
    from scripts.llm import LLMAuthError, LLMError, LLMRateLimitError, ask_json

    skill = (ROOT / "skills" / "explain-event" / "SKILL.md").read_text(encoding="utf-8")
    reports = {r["report_id"]: r for r in load_reports()}
    files = {p: json.loads(p.read_text(encoding="utf-8")) for p in sorted(EVENTS_DIR.glob("*.json"), reverse=True)}
    pending: dict[str, list[dict]] = defaultdict(list)
    for evs in files.values():
        for e in evs:
            if e.get("report_id") in reports and "reason_checked" not in e and e["type"] not in ("gap_above", "gap_below"):
                pending[e["report_id"]].append(e)
    done = 0
    failures = 0
    for rid in sorted(pending, key=lambda r: reports[r]["published_date"], reverse=True)[:max_reports]:
        r = reports[rid]
        evs = pending[rid]
        prompt = "\n\n".join([
            "너는 증권사 리포트에서 숫자 변화의 이유를 찾아 적는 파이프라인의 한 단계다. 아래 SKILL 명세를 따른다.",
            "=== SKILL: explain-event ===\n" + skill,
            f"=== 리포트 ===\n제목: {r['title']}\n발행일: {r['published_date']}",
            "=== 이벤트 ===\n" + json.dumps(
                [{"id": e["id"], "name": e["name"], "headline": e["headline"]} for e in evs],
                ensure_ascii=False, indent=1),
            "=== 원문 발췌 ===\n" + reason_excerpt(textstore.load_text(r) or r.get("preview_text") or ""),
        ])
        try:
            obj = ask_json(prompt)
        except (LLMAuthError, LLMRateLimitError) as e:
            global RATE_LIMITED
            RATE_LIMITED = RATE_LIMITED or isinstance(e, LLMRateLimitError)
            print(f"  ! 이유 생성 중단: {e}", flush=True)
            return done, True
        except LLMError as e:
            print(f"  ! {rid} 이유 생성 실패: {e}", flush=True)
            failures += 1
            if failures >= 3:
                return done, True
            continue
        reasons = obj.get("reasons") or {}
        for e in evs:
            val = reasons.get(e["id"])
            e["reason"] = val.strip() if isinstance(val, str) and val.strip() else None
            e["reason_checked"] = True
        done += 1
        print(f"[explain] {rid} 이벤트 {len(evs)}건", flush=True)
    for p, evs in files.items():
        write_json(p, evs)
    return done, False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--explain", type=int, default=0, help="이유가 없는 이벤트를 가진 리포트를 최대 N건 설명")
    args = ap.parse_args()
    build()
    if args.explain:
        _, aborted = explain_events(args.explain)
        return 1 if aborted else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
