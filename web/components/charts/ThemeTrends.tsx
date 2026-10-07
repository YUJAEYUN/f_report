import Link from "next/link";
import { weekLabel } from "@/lib/dashboard";

const W = 220, H = 74, BASE = H - 18;

/** 상위 테마별 최근 몇 주 언급 건수 추이 (작은 선 그래프 여러 개) */
export function ThemeTrends({ items, weeks }: { items: { name: string; values: number[]; badge: React.ReactNode }[]; weeks: string[] }) {
  const short = (w: string) => weekLabel(w).label.replace("주차", "주");
  return <div className="sm-grid">
    {items.map(({ name, values, badge }) => {
      const max = Math.max(...values, 1);
      const step = (W - 8) / Math.max(values.length - 1, 1);
      const pts = values.map((v, i) => [4 + i * step, BASE - (v / max) * (H - 30)] as const);
      const line = pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
      return <Link key={name} href={`/themes/${encodeURIComponent(name)}`} className="sm">
        <span className="sm-head"><b>{name}</b><span>{badge}</span></span>
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${name} 최근 ${values.length}주 추이: ${values.join(", ")}`}>
          <line x1={4} x2={W - 4} y1={BASE} y2={BASE} className="axis-line" />
          <polygon points={`4,${BASE} ${line} ${pts.at(-1)![0].toFixed(1)},${BASE}`} className="sm-area" />
          <polyline points={line} className="sm-line" />
          {pts.map(([x, y], i) => <circle key={i} cx={x} cy={y} r={i === pts.length - 1 ? 4 : 2.5}
            className={i === pts.length - 1 ? "sm-dot last" : "sm-dot"} data-tip={`${name} · ${weekLabel(weeks[i]).label} ${values[i]}건`} />)}
          <text x={4} y={H - 3} className="axis-text">{short(weeks[0])}</text>
          <text x={W - 4} y={H - 3} className="axis-text" textAnchor="end">{short(weeks.at(-1)!)}</text>
        </svg>
      </Link>;
    })}
  </div>;
}
