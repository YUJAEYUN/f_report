import Link from "next/link";
import { notFound } from "next/navigation";
import { allCards, decodeParam, digestDates, digestMarkdown } from "@/lib/data";
import { renderMarkdown } from "@/lib/md";
import { ReportList } from "@/components/ReportList";

export const dynamicParams = false;

export function generateStaticParams() {
  return digestDates().map((date) => ({ date }));
}

export default async function DailyPage({ params }: { params: Promise<{ date: string }> }) {
  const date = decodeParam((await params).date);
  const md = digestMarkdown(date);
  if (!md) notFound();
  const all = digestDates();
  const i = all.indexOf(date);
  const newer = i > 0 ? all[i - 1] : null;
  const older = i < all.length - 1 ? all[i + 1] : null;
  const cards = allCards().filter((c) => c.date === date);
  return (
    <>
      <h1>일간 다이제스트 {date}</h1>
      <article className="card prose" dangerouslySetInnerHTML={{ __html: renderMarkdown(md, { dropTitle: true }) }} />
      <section className="card">
        <h2>이 날 올라온 리포트 {cards.length}건</h2>
        <ReportList cards={cards} showDate={false} />
      </section>
      <div className="pager">
        {older ? <Link href={`/daily/${older}`}>← {older}</Link> : <span />}
        {newer ? <Link href={`/daily/${newer}`}>{newer} →</Link> : <span />}
      </div>
    </>
  );
}
