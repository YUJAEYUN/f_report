import Link from "next/link";

/** 가로 막대 목록 (이름 · 막대 · 건수) */
export function HBars({ rows, limit = 8 }: { rows: { name: string; value: number; href?: string }[]; limit?: number }) {
  const shown = rows.filter((r) => r.value > 0).slice(0, limit);
  if (!shown.length) return <p className="sub">없음</p>;
  const max = Math.max(...shown.map((r) => r.value));
  return <ul className="hbars">
    {shown.map((r) => {
      const body = <><span className="hb-name">{r.name}</span><span className="hb-bar"><span style={{ width: `${(r.value / max) * 100}%` }} /></span><span className="hb-val">{r.value}</span></>;
      return <li key={r.name}>{r.href ? <Link href={r.href} className="hb-row">{body}</Link> : <span className="hb-row">{body}</span>}</li>;
    })}
  </ul>;
}
