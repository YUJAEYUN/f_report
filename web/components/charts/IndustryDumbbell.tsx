import type { PeriodRow } from "@/lib/dashboard";

const W = 520, ROW = 34, X0 = 130, X1 = W - 40;

/** 산업별 언급 건수: 지난주 같은 기간(빈 점) → 이번 주(색 점) */
export function IndustryDumbbell({ rows }: { rows: PeriodRow[] }) {
  const max = Math.max(...rows.map((r) => Math.max(r.current, r.previous)), 1);
  const sx = (v: number) => X0 + (v / max) * (X1 - X0);
  return <svg viewBox={`0 0 ${W} ${16 + rows.length * ROW}`} className="dumbbell" role="img" aria-label="산업별 언급 건수, 지난주 같은 기간 대비">
    {rows.map((r, i) => {
      const cy = 16 + i * ROW;
      const cls = r.delta > 0 ? "up" : r.delta < 0 ? "down" : "flat";
      return <a key={r.name} href={`/industries/${encodeURIComponent(r.name)}`} data-tip={`${r.name} · 지난주 같은 기간 ${r.previous}건 → 이번 주 ${r.current}건`}>
        <rect x={0} y={cy - 15} width={W} height={ROW} fill="transparent" />
        <text x={0} y={cy + 5} className="db-label">{r.name}</text>
        <line x1={X0} x2={X1} y1={cy} y2={cy} className="db-track" />
        <line x1={sx(r.previous)} x2={sx(r.current)} y1={cy} y2={cy} className={`db-bar ${cls}`} />
        <circle cx={sx(r.previous)} cy={cy} r={5} className="db-prev" />
        <circle cx={sx(r.current)} cy={cy} r={6} className={`db-cur ${cls}`} />
        <text x={W} y={cy + 5} textAnchor="end" className="db-value">{r.current}</text>
      </a>;
    })}
  </svg>;
}
