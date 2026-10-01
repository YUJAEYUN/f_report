import Link from "next/link";
import type { ThemeChange } from "@/lib/dashboard";

const labels = { new: "신규", up: "확대", steady: "지속", down: "약화", dropped: "미등장" };
export function ThemeChangeList({ changes, week, limit }: { changes: ThemeChange[]; week: string; limit?: number }) {
  const rows = changes.filter((c) => c.status !== "dropped" && c.name !== "미분류").slice(0, limit);
  if (!rows.length) return <p className="empty">비교할 테마 변화가 없습니다.</p>;
  return <div className="change-list">
    {rows.map((c) => <Link href={`/themes/${encodeURIComponent(c.name)}?week=${week}`} className="change-row" key={c.name}>
      <span className={`trend trend-${c.status}`}>{labels[c.status]}</span>
      <strong>{c.name}</strong>
      <span className="change-count">{c.previous} → {c.current}건</span>
      <span className="delta">{c.delta > 0 ? "+" : ""}{c.delta}</span>
    </Link>)}
  </div>;
}
