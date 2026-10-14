import type { RatingChange, StockObservation, TimelinePoint } from "@/lib/signals";

const W = 720, H = 240, PAD_L = 64, PAD_R = 16, PAD_T = 18, PAD_B = 28;

const t = (d: string) => new Date(`${d}T00:00:00Z`).getTime();

/** 목표주가 계단 그래프 + 리포트에 적힌 현재주가 점 + 목표주가 변경 표시 */
export function TargetPriceChart({ timeline, observations, changes, today }: {
  timeline: TimelinePoint[]; observations: StockObservation[]; changes: RatingChange[]; today: string;
}) {
  const tps = timeline.filter((p) => p.target_price != null);
  const prices = observations.filter((o) => o.price != null);
  if (tps.length === 0) return <p className="sub" style={{ margin: 0 }}>목표주가 기록이 없습니다.</p>;

  const x0 = Math.min(t(timeline[0].date), ...prices.map((o) => t(o.date)));
  const x1 = Math.max(t(today), t(timeline.at(-1)!.date));
  const vals = [...tps.map((p) => p.target_price!), ...prices.map((o) => o.price!)];
  const lo = Math.min(...vals) * 0.9, hi = Math.max(...vals) * 1.05;
  const X = (d: string) => PAD_L + ((t(d) - x0) / Math.max(x1 - x0, 1)) * (W - PAD_L - PAD_R);
  const Y = (v: number) => PAD_T + (1 - (v - lo) / Math.max(hi - lo, 1)) * (H - PAD_T - PAD_B);

  // NR 구간에서는 선을 끊는다
  const segs: string[] = [];
  let cur = "";
  timeline.forEach((p, i) => {
    const next = timeline[i + 1]?.date ?? today;
    if (p.target_price == null || p.rating === "NR") { if (cur) segs.push(cur); cur = ""; return; }
    const y = Y(p.target_price).toFixed(1);
    cur += `${cur ? "L" : "M"}${X(p.date).toFixed(1)},${y} L${X(next).toFixed(1)},${y} `;
  });
  if (cur) segs.push(cur);

  const ticks = [lo, (lo + hi) / 2, hi];
  const fmt = (v: number) => v >= 10000
    ? `${(v / 10000).toLocaleString("ko-KR", { maximumFractionDigits: v >= 1e6 ? 0 : 1 })}만`
    : Math.round(v).toLocaleString("ko-KR");
  const yearTicks: string[] = [];
  for (let y = new Date(x0).getUTCFullYear() + 1; y <= new Date(x1).getUTCFullYear(); y++) yearTicks.push(`${y}-01-01`);

  return <svg viewBox={`0 0 ${W} ${H}`} className="tp-chart" role="img"
    aria-label={`목표주가 추이: ${tps.map((p) => `${p.date} ${p.target_price!.toLocaleString("ko-KR")}원`).join(", ")}`}>
    {ticks.map((v) => <g key={v}>
      <line x1={PAD_L} x2={W - PAD_R} y1={Y(v)} y2={Y(v)} className="grid-line" />
      <text x={PAD_L - 8} y={Y(v) + 4} textAnchor="end" className="axis-text">{fmt(v)}</text>
    </g>)}
    {yearTicks.map((d) => <g key={d}>
      <line x1={X(d)} x2={X(d)} y1={PAD_T} y2={H - PAD_B} className="grid-line" />
      <text x={X(d) + 4} y={H - 10} className="axis-text">{d.slice(0, 4)}</text>
    </g>)}
    {segs.map((d, i) => <path key={i} d={d} className="tp-line" />)}
    {changes.filter((c) => c.tp_to != null && c.tp_pct != null && !c.mismatch).map((c) => (
      <circle key={c.date} cx={X(c.date)} cy={Y(c.tp_to!)} r={4.5} className={`tp-mark ${c.tp_pct! > 0 ? "up" : "down"}`}
        data-tip={`${c.date} 목표주가 ${c.tp_from!.toLocaleString("ko-KR")} → ${c.tp_to!.toLocaleString("ko-KR")}원 (${c.tp_pct! > 0 ? "+" : ""}${c.tp_pct}%)`} />
    ))}
    {prices.map((o) => <circle key={o.date} cx={X(o.date)} cy={Y(o.price!)} r={3.5} className="px-dot"
      data-tip={`${o.date} 리포트 기준 주가 ${o.price!.toLocaleString("ko-KR")}원`} />)}
    <text x={W - PAD_R} y={H - 10} textAnchor="end" className="axis-text">{today.slice(5).replace("-", ".")}</text>
  </svg>;
}
