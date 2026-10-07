import Link from "next/link";
import { weekLabel } from "@/lib/dashboard";

export type HeatRow = { name: string; href: string; values: number[]; note?: React.ReactNode };

/** 행 = 테마/산업, 열 = 주. 칸 색이 진할수록 그 주에 많이 다뤘다. 언제 떠오르고 사그라드는지 보는 용도 */
export function WeekHeatmap({ rows, weeks, noteLabel }: { rows: HeatRow[]; weeks: string[]; noteLabel?: string }) {
  const max = Math.max(1, ...rows.flatMap((r) => r.values));
  return <div className="heat-scroll" tabIndex={0}>
    <div className="wheat" style={{ "--n": weeks.length, "--note": noteLabel ? "64px" : "0px" } as React.CSSProperties}>
      <span />
      {weeks.map((w) => <span key={w} className="wheat-head">{weekLabel(w).label.replace("주차", "주")}</span>)}
      {noteLabel && <span className="wheat-head">{noteLabel}</span>}
      {rows.map((r) => <div key={r.name} className="wheat-row">
        <Link href={r.href} className="wheat-name">{r.name}</Link>
        {r.values.map((v, i) => <span key={weeks[i]} className={`wheat-cell${v ? "" : " is-zero"}`}
          style={v ? { background: `color-mix(in srgb, var(--chart) ${Math.round(18 + (v / max) * 72)}%, var(--cell))`, color: v / max > 0.45 ? "#fff" : "var(--text)" } : undefined}
          data-tip={`${r.name} · ${weekLabel(weeks[i]).label} ${v}건`}>{v || ""}</span>)}
        {noteLabel && <span className="wheat-note">{r.note}</span>}
      </div>)}
    </div>
  </div>;
}
