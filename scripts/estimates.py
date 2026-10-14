"""리포트 원문(pdf_text)에서 투자의견·목표주가·실적 추정치·컨센서스를 결정적으로 뽑는다.

LLM을 쓰지 않는다. 하나증권 기업 리포트는 아래 블록이 정해진 모양으로 들어 있다.

  - 제목                 `SK하이닉스(000660.KS/매수): ...`
  - 페이지 머리말         `아이씨티케이 (456010)` (블록을 종목에 귀속시키는 기준)
  - 첫 장 박스           `BUY (유지)` / `목표주가(12M) 785,000원(유지)` / `현재 주가(10월13일) 612,000원`
  - Consensus Data      발행 시점의 시장 컨센서스 (연도 2개)
  - Financial Data      증권사 자체 추정치 (`2026F`처럼 F가 붙은 연도가 추정치)
  - 투자의견 변동 내역    규정상 들어가는 과거 투자의견·목표주가 이력표

산업 리포트에는 커버 종목마다 이력표가 여러 개 들어 있고, `하루에 하나` 같은 데일리
시리즈에는 기업 리포트가 여러 편 이어 붙어 있다. 그래서 블록을 리포트 단위가 아니라
"가장 가까운 앞쪽 머리말의 종목" 단위로 귀속시킨다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------- 공통 ----------

RATING_ALIASES = {
    "buy": "매수", "매수": "매수", "strong buy": "매수", "outperform": "매수",
    "neutral": "중립", "중립": "중립", "hold": "중립", "marketperform": "중립", "market perform": "중립",
    "reduce": "매도", "sell": "매도", "매도": "매도", "비중축소": "매도", "underperform": "매도",
    "not rated": "NR", "nr": "NR", "n/r": "NR",
    "overweight": "비중확대", "비중확대": "비중확대",
    "underweight": "비중축소",
}
# 의견 서열. 상향/하향 판정에 쓴다 (NR은 서열 밖 = 커버리지 시작/중단).
RATING_RANK = {"매도": 0, "중립": 1, "매수": 2}

STATUS_WORDS = ("유지", "상향", "하향", "신규", "재개")


def normalize_rating(raw: str | None) -> str | None:
    if not raw:
        return None
    key = re.sub(r"\s+", " ", raw.strip()).lower()
    return RATING_ALIASES.get(key)


def parse_number(tok: str) -> float | None:
    """`1,234.5` / `(2.0)`(음수) / `-`(없음) / `적지` 같은 표 셀을 숫자로."""
    t = tok.strip().replace(",", "")
    if not t or t in {"-", "–", "N/A", "n/a", "NA"}:
        return None
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def norm_name(name: str) -> str:
    return re.sub(r"\s+", "", name or "")


# ---------- 제목 ----------

_TITLE_RE = re.compile(
    r"^\s*(?P<name>[^()\[\]:]{1,40}?)\s*\(\s*(?P<code>\d{6})(?:\.(?P<mkt>K[SQ]))?\s*(?:/\s*(?P<rating>[^)]*))?\)"
)


def parse_title(title: str) -> dict | None:
    """`한미약품(128940.KS/BUY): ...` -> {name, code, market, rating}. 국내 6자리 코드만."""
    m = _TITLE_RE.match(title or "")
    if not m:
        return None
    return {
        "name": m.group("name").strip(),
        "code": m.group("code"),
        "market": m.group("mkt"),
        "rating": normalize_rating(m.group("rating")),
    }


# ---------- 머리말(블록 귀속) ----------

_HEADER_RE = re.compile(r"^[ \t]*([^\n()]{1,30}?)[ \t]*\((\d{6})\)[ \t]*$", re.M)


def company_headers(text: str) -> list[tuple[int, str, str]]:
    """본문의 `회사명 (123456)` 머리말 줄 위치 목록 (pos, name, code)."""
    out = []
    for m in _HEADER_RE.finditer(text or ""):
        name = m.group(1).strip()
        if not name or name[0] in "&-·":
            continue
        out.append((m.start(), name, m.group(2)))
    return out


# 머리말과 블록 사이 최대 거리(문자). 실측 중앙값 ~1,800, 정상 최대 ~2,600.
# 이보다 멀면 머리말이 인식되지 않은 다른 종목의 블록일 가능성이 높아 버린다.
MAX_OWNER_DISTANCE = 3000


def owner_at(headers: list[tuple[int, str, str]], pos: int,
             max_dist: int | None = None) -> tuple[str, str] | None:
    owner = None
    owner_pos = 0
    for hp, name, code in headers:
        if hp > pos:
            break
        owner, owner_pos = (name, code), hp
    if owner and max_dist is not None and pos - owner_pos > max_dist:
        return None
    return owner


# ---------- 첫 장 박스 ----------

_TP_RE = re.compile(r"목표주가\s*\(12M\)\s*([\d,]+)\s*원\s*(?:\(\s*([^)]{1,8})\s*\))?")
_PRICE_RE = re.compile(r"현재\s*주가\s*\(([^)]{1,12})\)\s*([\d,]+)\s*원")
_BOX_RATING_RE = re.compile(
    r"(BUY|Buy|Neutral|NEUTRAL|Reduce|REDUCE|Not Rated|매수|중립|매도)\s*(?:\(\s*([^)]{1,8})\s*\))?\s*$"
)


def _status(raw: str | None) -> str | None:
    if not raw:
        return None
    for w in STATUS_WORDS:
        if w in raw:
            return w
    return None


@dataclass
class TargetBox:
    pos: int
    rating: str | None
    rating_status: str | None
    target_price: float | None
    tp_status: str | None
    price: float | None


def parse_target_boxes(text: str) -> list[TargetBox]:
    out = []
    for m in _TP_RE.finditer(text or ""):
        before = text[max(0, m.start() - 200): m.start()].rstrip()
        rating = status = None
        lines = [ln.strip() for ln in before.split("\n") if ln.strip()]
        if lines:
            rm = _BOX_RATING_RE.search(lines[-1])
            if rm:
                rating, status = normalize_rating(rm.group(1)), _status(rm.group(2))
        pm = _PRICE_RE.search(text, m.end(), m.end() + 120)
        out.append(TargetBox(
            pos=m.start(),
            rating=rating,
            rating_status=status,
            target_price=parse_number(m.group(1)),
            tp_status=_status(m.group(2)),
            price=parse_number(pm.group(2)) if pm else None,
        ))
    return out


# ---------- Financial Data / Consensus Data ----------

# 표 행 이름 -> 표준 키. 위에서부터 처음 맞는 것을 쓴다 (`증가율` 등은 무시).
_ROW_KEYS: tuple[tuple[str, str], ...] = (
    ("매출액", "revenue"), ("매출", "revenue"), ("순영업수익", "revenue"), ("영업수익", "revenue"),
    ("영업이익", "op"),
    ("지배주주순이익", "net"), ("지배순이익", "net"), ("순이익", "net"), ("당기순이익", "net"),
    ("EPS", "eps"),
)
METRICS = ("revenue", "op", "net", "eps")


def _row_key(label: str) -> str | None:
    label = re.sub(r"\(.*?\)", "", label).strip()
    for prefix, key in _ROW_KEYS:
        if label == prefix:
            return key
    return None


_ROW_RE = re.compile(r"^\s*([A-Za-z가-힣/]+(?:\([^)]*\))?)\s+(.*?)\s*$")


def _parse_table(lines: list[str], years: list[str]) -> dict[str, dict[str, float | None]]:
    """years 순서대로 값을 맞춰 {year: {metric: value}}."""
    table: dict[str, dict[str, float | None]] = {y: {} for y in years}
    for ln in lines:
        m = _ROW_RE.match(ln)
        if not m:
            continue
        key = _row_key(m.group(1))
        if key is None or any(key in table[y] for y in years):
            continue
        toks = m.group(2).split()
        if len(toks) > len(years):
            toks = toks[-len(years):]
        if len(toks) != len(years):
            # 빈 칸(예: 보험사 매출액)은 값 없음으로 기록
            if not toks:
                for y in years:
                    table[y][key] = None
            continue
        for y, tok in zip(years, toks):
            table[y][key] = parse_number(tok)
    # 원문 표 자체의 오기 방어: 이익이 매출보다 크면 그 값은 버린다
    # (예: GS건설 리포트의 2027F 영업이익 칸에 매출액이 그대로 들어간 경우)
    for v in table.values():
        rev = v.get("revenue")
        if rev:
            for k in ("op", "net"):
                if v.get(k) is not None and abs(v[k]) >= abs(rev):
                    v[k] = None
    return {y: v for y, v in table.items() if any(x is not None for x in v.values())}


@dataclass
class EstimateBlock:
    pos: int
    kind: str  # "financial" | "consensus"
    values: dict[str, dict[str, float | None]] = field(default_factory=dict)  # year -> metric -> value
    forecast_years: list[str] = field(default_factory=list)


_FIN_HEAD_RE = re.compile(r"Financial Data\s*\(([^)]*)\)")
_YEARS_RE = re.compile(r"((?:20\d\d[AFE]?\s+){1,5}20\d\d[AFE]?)")


def parse_financial_blocks(text: str) -> list[EstimateBlock]:
    out = []
    for m in _FIN_HEAD_RE.finditer(text or ""):
        if "십억원" not in m.group(1):  # 원화(십억원) 표만. 해외 종목(CNY 등)은 건너뛴다.
            continue
        chunk = text[m.end(): m.end() + 1500]
        lines = chunk.split("\n")
        ym = None
        for i, ln in enumerate(lines[:3]):
            ym = _YEARS_RE.search(ln)
            if ym:
                body = lines[i + 1: i + 20]
                break
        if not ym:
            continue
        raw_years = ym.group(1).split()
        years = [y[:4] for y in raw_years]
        forecast = [y[:4] for y in raw_years if y.endswith(("F", "E"))]
        cut = []
        for ln in body:
            if "Analyst" in ln or "자료:" in ln:
                break
            cut.append(ln)
        values = _parse_table(cut, years)
        if values:
            out.append(EstimateBlock(m.start(), "financial", values, forecast))
    return out


def parse_consensus_blocks(text: str) -> list[EstimateBlock]:
    out = []
    for m in re.finditer(r"Consensus Data", text or ""):
        chunk = text[m.end(): m.end() + 600]
        lines = chunk.split("\n")
        ym = None
        for i, ln in enumerate(lines[:3]):
            ym = _YEARS_RE.search(ln)
            if ym:
                body = lines[i + 1: i + 8]
                break
        if not ym:
            continue
        years = [y[:4] for y in ym.group(1).split()]
        cut = []
        for ln in body:
            if "Stock Price" in ln:
                break
            cut.append(ln)
        values = _parse_table(cut, years)
        if values:
            out.append(EstimateBlock(m.start(), "consensus", values, years))
    return out


# ---------- 투자의견 변동 내역 표 ----------

HISTORY_HEAD = "투자의견 변동 내역 및 목표주가 괴리율"
_HIST_ROW_RE = re.compile(r"^\s*(\d{2})\.(\d{1,2})\.(\d{1,2})\s+(.*?)\s*$", re.M)
_HIST_NOTES = ("담당자 변경", "년 경과", "커버리지 제외")


@dataclass
class HistoryRow:
    date: str
    rating: str | None
    target_price: float | None
    note: str | None = None


@dataclass
class HistoryTable:
    pos: int
    name: str
    rows: list[HistoryRow]


def parse_history_tables(text: str) -> list[HistoryTable]:
    out = []
    t = text or ""
    starts = [m.start() for m in re.finditer(re.escape(HISTORY_HEAD), t)]
    for idx, s in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(t)
        seg = t[s + len(HISTORY_HEAD): end]
        seg = seg.split("Compliance")[0][:3000]
        name = ""
        for ln in seg.split("\n")[:4]:
            ln = ln.strip()
            if ln and not re.fullmatch(r"[\d\s.,%()원]+", ln) and not ln.startswith("날짜"):
                name = ln
                break
        rows = []
        for m in _HIST_ROW_RE.finditer(seg):
            yy, mm, dd, rest = m.groups()
            date = f"20{yy}-{int(mm):02d}-{int(dd):02d}"
            note = next((n for n in _HIST_NOTES if n in rest), None)
            if note:
                rows.append(HistoryRow(date, None, None, note))
                continue
            rm = re.match(r"(Not Rated|BUY|Buy|Neutral|Reduce|Hold|매수|중립|매도)\s*(.*)", rest)
            if not rm:
                continue
            toks = rm.group(2).split()
            tp = parse_number(toks[0]) if toks else None
            rows.append(HistoryRow(date, normalize_rating(rm.group(1)), tp))
        if name and rows:
            out.append(HistoryTable(s, name, rows))
    return out


# ---------- 리포트 1건 -> 종목별 관측 ----------

@dataclass
class Observation:
    code: str
    name: str
    report_id: str
    date: str
    title: str
    report_type: str
    primary: bool  # 제목의 종목 = 이 리포트의 주인공
    rating: str | None = None
    rating_status: str | None = None
    target_price: float | None = None
    tp_status: str | None = None
    price: float | None = None
    estimates: dict = field(default_factory=dict)       # year -> metric -> value (추정치 연도만)
    consensus: dict = field(default_factory=dict)       # year -> metric -> value

    def has_numbers(self) -> bool:
        return bool(self.target_price or self.estimates or self.consensus)


def extract(report: dict, name_map: dict[str, str]) -> tuple[list[Observation], list[tuple[str | None, str, HistoryTable]]]:
    """리포트 1건 -> (종목별 관측 목록, [(code, name, 이력표)])."""
    text = report.get("pdf_text") or ""
    title_info = parse_title(report.get("title", ""))
    headers = company_headers(text)
    # 제목의 종목코드에 오타가 있는 경우가 있다 (예: 코스맥스 192920 vs 본문 192820).
    # 본문 머리말의 회사명이 제목과 같으면 본문 코드를 믿는다.
    if title_info and headers and norm_name(headers[0][1]) == norm_name(title_info["name"]):
        title_info["code"] = headers[0][2]
    obs: dict[str, Observation] = {}

    def get(code: str, name: str) -> Observation:
        if code not in obs:
            obs[code] = Observation(
                code=code, name=name, report_id=report["report_id"],
                date=report.get("published_date", ""), title=report.get("title", ""),
                report_type=report.get("report_type", ""),
                primary=bool(title_info and title_info["code"] == code),
            )
        return obs[code]

    def owner(pos: int) -> tuple[str, str] | None:
        if not headers:  # 머리말이 하나도 없으면 제목의 종목으로
            return (title_info["name"], title_info["code"]) if title_info else None
        return owner_at(headers, pos, MAX_OWNER_DISTANCE)

    for box in parse_target_boxes(text):
        o = owner(box.pos)
        if not o:
            continue
        ob = get(o[1], o[0])
        if ob.target_price is None:
            ob.rating, ob.rating_status = box.rating, box.rating_status
            ob.target_price, ob.tp_status, ob.price = box.target_price, box.tp_status, box.price
    for blk in parse_financial_blocks(text):
        o = owner(blk.pos)
        if not o:
            continue
        ob = get(o[1], o[0])
        if not ob.estimates:
            ob.estimates = {y: v for y, v in blk.values.items() if y in blk.forecast_years}
    for blk in parse_consensus_blocks(text):
        o = owner(blk.pos)
        if not o:
            continue
        ob = get(o[1], o[0])
        if not ob.consensus:
            ob.consensus = blk.values

    # 제목의 의견은 박스를 못 읽었을 때만 보충
    if title_info and title_info["code"] in obs:
        ob = obs[title_info["code"]]
        ob.rating = ob.rating or title_info["rating"]

    tables = []
    for tbl in parse_history_tables(text):
        code = name_map.get(norm_name(tbl.name))
        if code is None:
            o = owner_at(headers, tbl.pos)
            if o and norm_name(o[0]) == norm_name(tbl.name):
                code = o[1]
        # 코드를 못 찾은 종목(산업 리포트에만 나온 종목 등)은 code=None으로 넘기고,
        # 호출 측이 회사명으로 묶는다.
        tables.append((code, tbl.name, tbl))

    return [o for o in obs.values() if o.has_numbers()], tables


def build_name_map(reports: list[dict]) -> dict[str, str]:
    """전체 리포트의 제목·머리말에서 `회사명 -> 종목코드`를 모은다."""
    name_map: dict[str, str] = {}
    # 본문 머리말이 제목보다 정확하므로 먼저 넣는다.
    for r in reports:
        for _, name, code in company_headers(r.get("pdf_text") or ""):
            name_map.setdefault(norm_name(name), code)
    for r in reports:
        ti = parse_title(r.get("title", ""))
        if ti:
            name_map.setdefault(norm_name(ti["name"]), ti["code"])
    return name_map
