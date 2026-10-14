import type { RatingChange, StockObservation, TimelinePoint, TpConsensusPoint } from "@/lib/signals";

const W = 720, H = 260, PAD_L = 64, PAD_R = 16, PAD_T = 18, PAD_B = 28;
const MAX_COLORED = 6; // 범주 색은 고정 순서 6개까지, 나머지 증권사는 "기타"(회색)로 접는다

const t = (d: string) => new Date(`${d}T00:00:00Z`).getTime();

/** 차트에 그릴 증권사 순서: 최근 관측이 많은 순으로 6곳까지 색, 이름 순 정렬로 색을 고정 */
export function brokerSlots(timeline: TimelinePoint[]): { colored: string[]; others: string[] } {
  const count = new Map<string, number>();
  for (const p of timeline) count.set(p.broker, (count.get(p.broker) ?? 0) + 1);
  const ranked = [...count.keys()].sort((a, b) => (count.get(b)! - count.get(a)!) || a.localeCompare(b, "ko"));
  const colored = ranked.slice(0, MAX_COLORED).sort((a, b) => a.localeCompare(b, "ko"));
  return { colored, others: ranked.slice(MAX_COLORED) };
}

/** 증권사별 목표주가 계단선 + 여러 증권사 평균(컨센서스) + 리포트에 적힌 당시 주가 */
export function TargetPriceChart({ timeline: allTimeline, observations, changes: allChanges, consensus: allConsensus, today, from }: {
  timeline: TimelinePoint[]; observations: StockObservation[]; changes: RatingChange[];
  consensus: TpConsensusPoint[]; today: string; from?: string;
}) {
  // from 이전 기록은 잘라 내되, 각 증권사의 그 시점 목표주가는 from에서 이어지도록 마지막 값을 끌어온다
  const clip = <T extends { date: string }>(xs: T[], key: (x: T) => string) => {
    if (!from) return xs;
    const carried = new Map<string, T>();
    for (const x of xs) if (x.date < from) carried.set(key(x), { ...x, date: from });
    return [...carried.values(), ...xs.filter((x) => x.date >= from)];
  };
  const timeline = clip(allTimeline, (p) => p.broker);
  const consensus = clip(allConsensus, () => "c");
  const changes = from ? allChanges.filter((c) => c.date >= from) : allChanges;
  const tps = timeline.filter((p) => p.target_price != null);
  const prices = observations.filter((o) => o.price != null && (!from || o.date >= from));
  if (tps.length === 0) return <p className="sub" style={{ margin: 0 }}>목표주가 기록이 없습니다.</p>;
  const { colored, others } = brokerSlots(timeline);
  const showCons = colored.length + others.length >= 2 && consensus.some((c) => c.n >= 2);

  const x0 = Math.min(t(timeline[0].date), ...prices.map((o) => t(o.date)));
  // 오른쪽 여백: 마지막 날 새로 나온 목표주가도 짧은 선으로 보이게
  const xEnd = Math.max(t(today), t(timeline.at(-1)!.date));
  const x1 = xEnd + Math.max((xEnd - x0) * 0.04, 2 * 86400000);
  const vals = [...tps.map((p) => p.target_price!), ...prices.map((o) => o.price!)];
  const lo = Math.min(...vals) * 0.9, hi = Math.max(...vals) * 1.05;
  const X = (d: string) => PAD_L + ((t(d) - x0) / Math.max(x1 - x0, 1)) * (W - PAD_L - PAD_R);
  const Y = (v: number) => PAD_T + (1 - (v - lo) / Math.max(hi - lo, 1)) * (H - PAD_T - PAD_B);

  // 증권사별 계단선. NR 구간에서는 선을 끊는다
  const endDate = new Date(x1).toISOString().slice(0, 10);
  const stepPath = (pts: { date: string; v: number | null }[]) => {
    const segs: string[] = [];
    let cur = "";
    pts.forEach((p, i) => {
      const next = pts[i + 1]?.date ?? endDate;
      if (p.v == null) { if (cur) segs.push(cur); cur = ""; return; }
      const y = Y(p.v).toFixed(1);
      cur += `${cur ? "L" : "M"}${X(p.date).toFixed(1)},${y} L${X(next).toFixed(1)},${y} `;
    });
    if (cur) segs.push(cur);
    return segs.join(" ");
  };
  const lineOf = (b: string) => stepPath(timeline.filter((p) => p.broker === b)
    .map((p) => ({ date: p.date, v: p.rating === "NR" ? null : p.target_price })));

  const ticks = [lo, (lo + hi) / 2, hi];
  const fmt = (v: number) => v >= 10000
    ? `${(v / 10000).toLocaleString("ko-KR", { maximumFractionDigits: v >= 1e6 ? 0 : 1 })}만`
    : Math.round(v).toLocaleString("ko-KR");
  // 기간이 1년 이하면 월 눈금, 길면 연 눈금
  const yearTicks: string[] = [];
  const short = x1 - x0 <= 400 * 86400000;
  const cur = new Date(x0); cur.setUTCDate(1);
  for (cur.setUTCMonth(cur.getUTCMonth() + 1); cur.getTime() <= x1; cur.setUTCMonth(cur.getUTCMonth() + 1)) {
    if (short || cur.getUTCMonth() === 0) yearTicks.push(cur.toISOString().slice(0, 10));
  }
  const tickLabel = (d: string) => short ? `${Number(d.slice(5, 7))}월` : d.slice(0, 4);
  const slot = (b: string) => colored.indexOf(b);

  return <>
    <svg viewBox={`0 0 ${W} ${H}`} className="tp-chart" role="img"
      aria-label={`증권사별 목표주가 추이: ${colored.join(", ")}${others.length ? ` 외 ${others.length}곳` : ""}`}>
      {ticks.map((v) => <g key={v}>
        <line x1={PAD_L} x2={W - PAD_R} y1={Y(v)} y2={Y(v)} className="grid-line" />
        <text x={PAD_L - 8} y={Y(v) + 4} textAnchor="end" className="axis-text">{fmt(v)}</text>
      </g>)}
      {yearTicks.map((d) => <g key={d}>
        <line x1={X(d)} x2={X(d)} y1={PAD_T} y2={H - PAD_B} className="grid-line" />
        <text x={X(d) + 4} y={H - 10} className="axis-text">{tickLabel(d)}</text>
      </g>)}
      {others.map((b) => <path key={b} d={lineOf(b)} className="tp-line other" />)}
      {colored.map((b) => <path key={b} d={lineOf(b)} className={`tp-line s${slot(b) + 1}`} />)}
      {colored.map((b) => {
        const last = timeline.filter((p) => p.broker === b).at(-1);
        if (!last || last.target_price == null || last.rating === "NR") return null;
        return <circle key={`end-${b}`} cx={X(last.date)} cy={Y(last.target_price)} r={3.5} className={`tp-end s${slot(b) + 1}`}
          data-tip={`${b} ${last.date} 목표주가 ${last.target_price.toLocaleString("ko-KR")}원 (${last.rating})`} />;
      })}
      {showCons && <path className="tp-cons" d={stepPath(consensus.filter((c) => c.n >= 2).map((c) => ({ date: c.date, v: c.mean })))} />}
      {showCons && consensus.filter((c) => c.n >= 2).map((c) => <circle key={c.date} cx={X(c.date)} cy={Y(c.mean)} r={6} className="hit"
        data-tip={`${c.date} 컨센서스 ${c.mean.toLocaleString("ko-KR")}원 (${c.n}개사: ${Object.entries(c.brokers).map(([b, v]) => `${b} ${v.toLocaleString("ko-KR")}`).join(", ")})`} />)}
      {changes.filter((c) => c.tp_to != null && c.tp_pct != null && !c.mismatch).map((c) => (
        <circle key={`${c.date}-${c.broker}`} cx={X(c.date)} cy={Y(c.tp_to!)} r={4.5} className={`tp-mark ${c.tp_pct! > 0 ? "up" : "down"}`}
          data-tip={`${c.date} ${c.broker} 목표주가 ${c.tp_from!.toLocaleString("ko-KR")} → ${c.tp_to!.toLocaleString("ko-KR")}원 (${c.tp_pct! > 0 ? "+" : ""}${c.tp_pct}%)`} />
      ))}
      {prices.map((o) => <circle key={`${o.date}-${o.broker}`} cx={X(o.date)} cy={Y(o.price!)} r={3.5} className="px-dot"
        data-tip={`${o.date} ${o.broker} 리포트 기준 주가 ${o.price!.toLocaleString("ko-KR")}원`} />)}
      <text x={W - PAD_R} y={H - 10} textAnchor="end" className="axis-text">{today.slice(5).replace("-", ".")}</text>
    </svg>
    <p className="legend tp-legend">
      {showCons && <span><i className="sw cons" />컨센서스(평균)</span>}
      {colored.map((b) => <span key={b}><i className={`sw s${slot(b) + 1}`} />{b}</span>)}
      {others.length > 0 && <span><i className="sw other" />기타 {others.length}곳</span>}
      <span><i className="sw px" />당시 주가</span>
    </p>
  </>;
}
