import Link from "next/link";
import { notFound } from "next/navigation";
import { dashboardSnapshot, decodeParam, weeklyMarkdown, weeklyMeta, weeks } from "@/lib/data";
import { themeChanges, weekLabel } from "@/lib/dashboard";
import { ThemeChangeList } from "@/components/dashboard/ThemeChangeList";
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
  const changes = themeChanges(dashboardSnapshot(), week);
  const wl = weekLabel(week);
  const year = week.slice(0, 4);
  return (
    <>
      <p className="eyebrow">WEEKLY INSIGHT</p>
      <h1>{wl.label} 주간 인사이트</h1>
      <p className="sub">
        {year}. {wl.range}
        {meta && ` · 개별 리포트 ${meta.report_count}건 기준`} · <span title="ISO 주차">{week}</span>
      </p>
      <section className="card dashboard-card">
        <div className="card-head"><h2>직전 주 대비 테마 변화</h2><span className="count">개별 리포트 언급량 기준</span></div>
        <ThemeChangeList changes={changes} week={week} />
      </section>
      <article className="card prose" dangerouslySetInnerHTML={{ __html: renderMarkdown(md, { dropTitle: true }) }} />
      <div className="pager">
        {older ? <Link href={`/weekly/${older}`}>← {weekLabel(older).label}</Link> : <span />}
        {newer ? <Link href={`/weekly/${newer}`}>{weekLabel(newer).label} →</Link> : <span />}
      </div>
    </>
  );
}
