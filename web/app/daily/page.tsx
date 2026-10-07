import Link from "next/link";
import { allCards, digestDates, digestMarkdown, section } from "@/lib/data";

const WD = ["일", "월", "화", "수", "목", "금", "토"];

export default function DailyIndex() {
  const cards = allCards();
  const rows = digestDates().map((d) => {
    const md = digestMarkdown(d) ?? "";
    const headline = section(md, /오늘 한 줄/)?.replace(/^[-*>\s]+/, "") ?? null;
    const n = cards.filter((c) => c.date === d && c.type === "individual").length;
    return { d, headline, n, date: new Date(`${d}T00:00:00Z`) };
  });
  const max = Math.max(1, ...rows.map((r) => r.n));
  const months: { month: string; rows: typeof rows }[] = [];
  for (const r of rows) {
    const m = `${r.date.getUTCFullYear()}년 ${r.date.getUTCMonth() + 1}월`;
    const last = months.at(-1);
    if (last?.month === m) last.rows.push(r); else months.push({ month: m, rows: [r] });
  }
  return <>
    <h1 className="page-title">일간 다이제스트</h1>
    <p className="sub">발행일마다 그날 리서치에서 많이 나온 이야기를 쉬운 말로 정리합니다.</p>
    {months.map((m) => <section key={m.month} className="week-month">
      <h2>{m.month}</h2>
      <ul className="week-list">
        {m.rows.map((r) => <li key={r.d}>
          <Link href={`/daily/${r.d}`} className="week-row">
            <span className="week-when"><strong>{r.date.getUTCMonth() + 1}월 {r.date.getUTCDate()}일</strong><span className="week-range">{WD[r.date.getUTCDay()]}요일</span></span>
            <span className="week-bar" aria-hidden="true"><span style={{ width: `${(r.n / max) * 100}%` }} /></span>
            <span className="week-count">개별 {r.n}건</span>
            {r.headline && <span className="week-themes">{r.headline}</span>}
          </Link>
        </li>)}
      </ul>
    </section>)}
  </>;
}
