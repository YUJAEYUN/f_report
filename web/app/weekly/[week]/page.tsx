import Link from "next/link";
import { notFound } from "next/navigation";
import { decodeParam, weeklyMarkdown, weeklyMeta, weeks } from "@/lib/data";
import { renderMarkdown } from "@/lib/md";

export const dynamicParams = false;

export function generateStaticParams() {
  return weeks().map((week) => ({ week }));
}

export default async function WeeklyPage({ params }: { params: Promise<{ week: string }> }) {
  const week = decodeParam((await params).week);
  const md = weeklyMarkdown(week);
  if (!md) notFound();
  const meta = weeklyMeta(week);
  const all = weeks();
  const i = all.indexOf(week);
  const newer = i > 0 ? all[i - 1] : null;
  const older = i < all.length - 1 ? all[i + 1] : null;
  return (
    <>
      <h1>주간 인사이트 {week}</h1>
      {meta && <p className="sub">individual 리포트 {meta.report_count}건 기준</p>}
      <article className="card prose" dangerouslySetInnerHTML={{ __html: renderMarkdown(md, { dropTitle: true }) }} />
      <div className="pager">
        {older ? <Link href={`/weekly/${older}`}>← {older}</Link> : <span />}
        {newer ? <Link href={`/weekly/${newer}`}>{newer} →</Link> : <span />}
      </div>
    </>
  );
}
