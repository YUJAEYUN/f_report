import Link from "next/link";
import { allCards, countBy } from "@/lib/data";

export default function ThemesIndex() {
  const cards = allCards();
  const themes = countBy(cards, "themes");
  const latest = cards[0]?.date;
  return (
    <>
      <h1>테마</h1>
      <p className="sub">산업을 가로지르는 이슈. 여러 리포트에 걸쳐 나온 순서대로</p>
      <div className="chips">
        {themes.map(([name, n]) => (
          <Link key={name} className="chip theme" href={`/themes/${encodeURIComponent(name)}`}>
            {name}<span className="n">{n}</span>
          </Link>
        ))}
      </div>
      {latest && <p className="count" style={{ marginTop: 16 }}>최신 리포트 {latest} 기준</p>}
    </>
  );
}
