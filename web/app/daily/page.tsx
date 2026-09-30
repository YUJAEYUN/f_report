import Link from "next/link";
import { allCards, digestDates } from "@/lib/data";

export default function DailyIndex() {
  const cards = allCards();
  return (
    <>
      <h1>일간 다이제스트</h1>
      <p className="sub">발행일별 핵심 3줄 · 데일리 코멘트 · 개별 리포트</p>
      <ul className="list-plain">
        {digestDates().map((d) => (
          <li key={d}>
            <Link href={`/daily/${d}`}>{d}</Link>
            <span className="count">리포트 {cards.filter((c) => c.date === d).length}건</span>
          </li>
        ))}
      </ul>
    </>
  );
}
