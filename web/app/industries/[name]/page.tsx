import Link from "next/link";
import { notFound } from "next/navigation";
import { allCards, countBy, decodeParam, industryBriefs, taxonomy } from "@/lib/data";
import { renderMarkdown } from "@/lib/md";
import { ReportList } from "@/components/ReportList";

export const dynamicParams = false;

export function generateStaticParams() {
  return countBy(allCards(), "industries").map(([name]) => ({ name }));
}

export default async function IndustryPage({ params }: { params: Promise<{ name: string }> }) {
  const name = decodeParam((await params).name);
  const cards = allCards().filter((c) => c.industries.includes(name));
  if (cards.length === 0) notFound();
  const briefs = industryBriefs(name);
  const themes = countBy(cards, "themes");
  return (
    <>
      <p className="sub"><Link href="/industries">산업</Link></p>
      <h1>{name}</h1>
      <p className="sub">{taxonomy().industries[name]} · 리포트 {cards.length}건</p>
      {themes.length > 0 && (
        <div className="chips">
          {themes.map(([t, n]) => (
            <Link key={t} className="chip theme" href={`/themes/${encodeURIComponent(t)}`}>{t}<span className="n">{n}</span></Link>
          ))}
        </div>
      )}
      {briefs.map((b) => (
        <details key={b.week} id={b.week} className="card" open={b === briefs[0]}>
          <summary><strong>{b.week} 브리핑</strong></summary>
          <div className="prose" dangerouslySetInnerHTML={{ __html: renderMarkdown(b.markdown, { dropTitle: true }) }} />
        </details>
      ))}
      <section className="card">
        <h2 style={{ marginTop: 0 }}>리포트</h2>
        <ReportList cards={cards} />
      </section>
    </>
  );
}
