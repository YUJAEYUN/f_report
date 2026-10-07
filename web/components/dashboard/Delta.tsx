import type { PeriodRow } from "@/lib/dashboard";

/** 지난주 같은 기간 대비 증감. 한국 시장 관례대로 상승 빨강, 하락 파랑 */
export function Delta({ row }: { row: PeriodRow }) {
  if (row.previous === 0) return <span className="delta-badge up">신규</span>;
  if (row.delta === 0) return <span className="delta-badge">–</span>;
  return <span className={`delta-badge ${row.delta > 0 ? "up" : "down"}`}>{row.delta > 0 ? "▲" : "▼"}{Math.abs(row.delta)}</span>;
}
