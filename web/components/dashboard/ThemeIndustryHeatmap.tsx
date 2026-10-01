import Link from "next/link";
import type { ThemeIndustryCell } from "@/lib/dashboard";

export function ThemeIndustryHeatmap({ cells, week, themes, industries }: { cells: ThemeIndustryCell[]; week: string; themes: string[]; industries: string[] }) {
  const map = new Map(cells.map((c) => [`${c.theme}\0${c.industry}`, c.count]));
  const max = Math.max(1, ...cells.map((c) => c.count));
  return <div className="heatmap-scroll" tabIndex={0} aria-label="테마와 산업 공동 언급 표">
    <div className="heatmap" style={{ gridTemplateColumns: `minmax(150px, 1.5fr) repeat(${industries.length}, minmax(72px, 1fr))` }}>
      <span />{industries.map((i) => <strong className="heat-label" key={i}>{i}</strong>)}
      {themes.flatMap((theme) => [
        <strong className="heat-theme" key={`${theme}-label`}>{theme}</strong>,
        ...industries.map((industry) => {
          const count = map.get(`${theme}\0${industry}`) ?? 0;
          const strength = Math.round(25 + (count / max) * 75);
          return count ? <Link key={`${theme}-${industry}`} className="heat-cell" style={{ background: `color-mix(in srgb, var(--chart) ${strength}%, var(--surface))` }} title={`${theme} × ${industry}: ${count}건`} href={`/reports?week=${week}&theme=${encodeURIComponent(theme)}&industry=${encodeURIComponent(industry)}`}>{count}</Link>
            : <span key={`${theme}-${industry}`} className="heat-cell heat-empty">0</span>;
        }),
      ])}
    </div>
  </div>;
}
