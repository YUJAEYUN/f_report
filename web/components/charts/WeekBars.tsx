import { weekLabel } from "@/lib/dashboard";

const H = 150, BASE = H - 22;

/** 주별 건수 막대. 마지막(가장 최근) 주를 강조한다 */
export function WeekBars({ values, weeks, unit = "건" }: { values: number[]; weeks: string[]; unit?: string }) {
  const W = Math.max(300, weeks.length * 64);
  const max = Math.max(...values, 1);
  const gw = W / weeks.length;
  return <svg viewBox={`0 0 ${W} ${H}`} className="week-bars" role="img" aria-label={`주별 건수: ${values.join(", ")}`}>
    <line x1={0} x2={W} y1={BASE} y2={BASE} className="axis-line" />
    {values.map((v, i) => {
      const h = (v / max) * (BASE - 22);
      const cx = i * gw + gw / 2;
      const last = i === values.length - 1;
      return <g key={weeks[i]} data-tip={`${weekLabel(weeks[i]).label} · ${v}${unit}`}>
        <rect x={cx - 14} y={BASE - h} width={28} height={Math.max(h, v ? 2 : 0)} rx={4} className={last ? "wb-bar last" : "wb-bar"} />
        {v > 0 && <text x={cx} y={BASE - h - 6} textAnchor="middle" className="wb-val">{v}</text>}
        <text x={cx} y={H - 5} textAnchor="middle" className="axis-text">{weekLabel(weeks[i]).label.replace("주차", "주")}</text>
      </g>;
    })}
  </svg>;
}
