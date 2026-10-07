import type { PeriodRow } from "@/lib/dashboard";
import { squarify } from "@/lib/treemap";

function tone(t: PeriodRow): { color: string; pct: number } {
  if (t.previous === 0) return { color: "var(--up)", pct: 72 };
  if (t.delta > 0) return { color: "var(--up)", pct: 25 + Math.min(t.delta / 9, 1) * 60 };
  if (t.delta < 0) return { color: "var(--down)", pct: 25 + Math.min(-t.delta / 5, 1) * 55 };
  return { color: "var(--text)", pct: 9 };
}

function change(t: PeriodRow) {
  if (t.previous === 0) return "신규";
  if (t.delta === 0) return "–";
  return `${t.delta > 0 ? "▲" : "▼"}${Math.abs(t.delta)}`;
}

function TreemapSvg({ rows, width, height, week, className }: { rows: PeriodRow[]; width: number; height: number; week: string; className: string }) {
  const cells = squarify(rows.map((r) => ({ value: r.current, item: r })), width, height);
  return <svg viewBox={`0 0 ${width} ${height}`} className={`treemap ${className}`} role="img" aria-label="이번 주 테마별 언급 건수와 지난주 같은 기간 대비 변화">
    {cells.map(({ x, y, w, h, item: t }) => {
      const { color, pct } = tone(t);
      const fg = pct >= 55 ? "#fff" : "var(--text)";
      const fs = w * h > 30000 ? 15 : w * h > 9000 ? 13 : 11.5;
      const maxChars = Math.max(Math.floor((w - 16) / (fs * 0.95)), 2);
      const name = t.name.length > maxChars ? `${t.name.slice(0, maxChars - 1)}…` : t.name;
      const tip = `${t.name} · ${t.current}건 · ${t.previous === 0 ? "신규" : `지난주 같은 기간 ${t.previous}건`}`;
      return <a key={t.name} href={`/themes/${encodeURIComponent(t.name)}?week=${week}`} data-tip={tip} aria-label={tip}>
        <rect x={x + 1} y={y + 1} width={Math.max(w - 2, 0)} height={Math.max(h - 2, 0)} rx={4}
          style={{ fill: `color-mix(in srgb, ${color} ${Math.round(pct)}%, var(--cell))` }} />
        {w > 70 && h > 34 && <>
          <text x={x + 10} y={y + 10 + fs} fontSize={fs} fontWeight={700} style={{ fill: fg }}>{name}</text>
          <text x={x + 10} y={y + 14 + fs * 2.1} fontSize={fs * 0.82} style={{ fill: fg, opacity: 0.85 }}>{t.current}건 · {change(t)}</text>
        </>}
      </a>;
    })}
  </svg>;
}

/** 면적 = 이번 주 언급 건수, 색 = 지난주 같은 기간 대비 (빨강 증가 / 파랑 감소). 넓은 화면·좁은 화면용 두 배치 */
export function ThemeTreemap({ rows, week }: { rows: PeriodRow[]; week: string }) {
  return <>
    <TreemapSvg rows={rows} width={760} height={580} week={week} className="tm-wide" />
    <TreemapSvg rows={rows} width={360} height={470} week={week} className="tm-narrow" />
  </>;
}
