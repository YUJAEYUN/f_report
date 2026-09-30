import Link from "next/link";
import { notFound } from "next/navigation";
import { allCards, countBy, decodeParam, isoWeek, weeklyMeta } from "@/lib/data";
import { ReportList } from "@/components/ReportList";

export const dynamicParams = false;

export function generateStaticParams() {
  return countBy(allCards(), "themes").map(([name]) => ({ name }));
}

export default async function ThemePage({ params }: { params: Promise<{ name: string }> }) {
  const name = decodeParam((await params).name);
  const cards = allCards().filter((c) => c.themes.includes(name));
  if (cards.length === 0) notFound();
  const byWeek = new Map<string, typeof cards>();
  for (const c of cards) {
    const w = isoWeek(c.date);
    byWeek.set(w, [...(byWeek.get(w) ?? []), c]);
  }
  const industries = countBy(cards, "industries");
  return (
    <>
      <p className="sub"><Link href="/themes">테마</Link></p>
      <h1>{name}</h1>
      <p className="sub">리포트 {cards.length}건 · {byWeek.size}개 주에 걸쳐 등장</p>
      {industries.length > 0 && (
        <div className="chips">
          {industries.map(([i, n]) => (
            <Link key={i} className="chip" href={`/industries/${encodeURIComponent(i)}`}>{i}<span className="n">{n}</span></Link>
          ))}
        </div>
      )}
      {[...byWeek.entries()].map(([week, list]) => {
        const inTop = weeklyMeta(week)?.themes.some((t) => t.name === name);
        return (
          <section key={week} className="card">
            <div className="card-head">
              <h2>{week}</h2>
              {inTop && <Link href={`/weekly/${week}`}>이 주 인사이트에서 다룸 →</Link>}
            </div>
            <ReportList cards={list} />
          </section>
        );
      })}
    </>
  );
}
