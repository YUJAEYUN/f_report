import Link from "next/link";
import { allCards, countBy, taxonomy } from "@/lib/data";

export default function IndustriesIndex() {
  const counts = new Map(countBy(allCards(), "industries"));
  const tax = taxonomy().industries;
  return (
    <>
      <h1>산업</h1>
      <p className="sub">리포트가 주제로 다룬 산업. 한 주에 2건 이상 모이면 브리핑이 생긴다</p>
      <ul className="list-plain">
        {Object.entries(tax).map(([name, desc]) => {
          const n = counts.get(name) ?? 0;
          return (
            <li key={name}>
              <span>
                {n > 0 ? <Link href={`/industries/${encodeURIComponent(name)}`}>{name}</Link> : <span className="count">{name}</span>}
                <span className="count"> · {desc}</span>
              </span>
              <span className="count">{n}건</span>
            </li>
          );
        })}
      </ul>
    </>
  );
}
