import Link from "next/link";
import type { PeriodRow } from "@/lib/dashboard";

/** 이름 · 막대 · 건수 · 직전 같은 기간 대비 증감 */
export function RankBars({ rows, hrefFor, limit = 6 }: { rows: PeriodRow[]; hrefFor: (name: string) => string; limit?: number }) {
  const shown = rows.filter((r) => r.current > 0).slice(0, limit);
  if (!shown.length) return <p className="empty">이번 주 집계가 아직 없습니다.</p>;
  const max = Math.max(...shown.map((r) => r.current));
  return <ol className="rank-bars">
    {shown.map((r) => (
      <li key={r.name}>
        <Link href={hrefFor(r.name)} className="rank-row">
          <span className="rank-name">{r.name}</span>
          <span className="rank-bar" aria-hidden="true"><span style={{ width: `${(r.current / max) * 100}%` }} /></span>
          <span className="rank-count">{r.current}건</span>
          <Delta row={r} />
        </Link>
      </li>
    ))}
  </ol>;
}

export function Delta({ row }: { row: PeriodRow }) {
  if (row.previous === 0) return <span className="rank-delta is-new">신규</span>;
  if (row.delta === 0) return <span className="rank-delta">–</span>;
  return <span className={`rank-delta ${row.delta > 0 ? "is-up" : "is-down"}`}>{row.delta > 0 ? "▲" : "▼"}{Math.abs(row.delta)}</span>;
}
