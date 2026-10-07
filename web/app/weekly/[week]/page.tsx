import Link from "next/link";
import { notFound } from "next/navigation";
import { allReports, dashboardSnapshot, decodeParam, headlineOf, resolveTheme, section, weeklyMarkdown, weeks } from "@/lib/data";
import { comparePeriods, weekLabel } from "@/lib/dashboard";
import { renderMarkdown, subsections } from "@/lib/md";
import ChartTooltip from "@/components/charts/ChartTooltip";
import { IndustryDumbbell } from "@/components/charts/IndustryDumbbell";
import { ThemeTreemap } from "@/components/charts/ThemeTreemap";
import { TrendChart } from "@/components/charts/ThemeTrends";
import { Delta } from "@/components/dashboard/Delta";

export const dynamicParams = false;

export function generateStaticParams() {
  return weeks().map((week) => ({ week }));
}

export default async function WeeklyPage({ params }: { params: Promise<{ week: string }> }) {
  const week = decodeParam((await params).week);
  const md = weeklyMarkdown(week);
  if (!md) notFound();
  const all = weeks();
  const i = all.indexOf(week);
  const newer = i > 0 ? all[i - 1] : null;
  const older = i < all.length - 1 ? all[i + 1] : null;
  const wl = weekLabel(week);

  const snapshot = dashboardSnapshot();
  const thisWeek = snapshot.weeks.find((w) => w.week === week);
  // 진행 중인 주든 지난 주든, 그 주의 마지막 발행일까지를 지난주 같은 기간과 비교한다
  const cmp = thisWeek ? comparePeriods(allReports(), week, thisWeek.throughDate) : null;
  const trendWeeks = snapshot.weeks.filter((w) => w.week <= week).slice(0, 4).map((w) => w.week).reverse();
  const weekCount = (w: string, name: string) => snapshot.weeks.find((x) => x.week === w)?.themes.find((t) => t.name === name)?.count ?? 0;

  const { headline, lead } = headlineOf(md);
  const themes = subsections(section(md, /이번 주 테마/) ?? "");
  const industryFlow = section(md, /산업 흐름/);
  const checkpoints = section(md, /체크포인트/);
  const mapRows = cmp?.themes.filter((t) => t.current >= 2).slice(0, 16) ?? [];
  const singles = cmp?.themes.filter((t) => t.current === 1).length ?? 0;
  const reportDelta = cmp ? cmp.reports.current - cmp.reports.previous : 0;
  const dumbbell = cmp?.industries.filter((r) => r.current > 0 || r.previous > 0).slice(0, 9) ?? [];
  const neighbor = (w: string | null, dir: "older" | "newer") => w && <Link href={`/weekly/${w}`} className={`week-nav-${dir}`}>
    <span>{dir === "older" ? "← 이전 주" : "다음 주 →"} · {weekLabel(w).label}</span>
    <b>{headlineOf(weeklyMarkdown(w)).headline}</b>
  </Link>;

  return <>
    <p className="page-when">
      주간 인사이트 · {week.slice(0, 4)}. {wl.range}{cmp && ` · 개별 리포트 ${cmp.reports.current}건`}
      <span className="week-jump">
        {older ? <Link href={`/weekly/${older}`}>← {weekLabel(older).label}</Link> : null}
        {newer ? <Link href={`/weekly/${newer}`}>{weekLabel(newer).label} →</Link> : null}
      </span>
    </p>

    <div className="map-hero">
      <section className="panel">
        <h2>{wl.label} 테마 지도</h2>
        <p className="hint">면적은 언급 건수, 색은 지난주 같은 기간 대비 변화입니다. 빨강 증가 · 파랑 감소 · 진한 빨강 신규. 2건 이상 테마만, 1건짜리 {singles}개는 제외.</p>
        {mapRows.length > 0 ? <ThemeTreemap rows={mapRows} week={week} /> : <p className="sub">이 주의 테마 집계가 없습니다.</p>}
      </section>
      <section className="panel">
        <h2>{wl.label} 한 줄</h2>
        {headline && <h1 className="headline">{headline}</h1>}
        {lead && <p className="lead">{lead}</p>}
        {cmp && <div className="big-numbers">
          <div><span>개별 리포트</span><strong>{cmp.reports.current}</strong>
            {reportDelta !== 0 && <em className={reportDelta > 0 ? "up" : "down"}>{reportDelta > 0 ? "▲" : "▼"}{Math.abs(reportDelta)}</em>}</div>
          <div><span>테마 (2건 이상)</span><strong>{mapRows.length}</strong></div>
          <div><span>신규 테마</span><strong>{mapRows.filter((t) => t.previous === 0).length}</strong></div>
        </div>}
        {checkpoints && <>
          <h2 className="sub-title">다음 주 볼 것</h2>
          <div className="prose checklist" dangerouslySetInnerHTML={{ __html: renderMarkdown(checkpoints) }} />
        </>}
      </section>
    </div>

    {themes.length > 0 && <>
      <div className="section-head"><h2>이번 주 테마</h2><span>최근 {trendWeeks.length}주 언급 추이와 함께</span></div>
      {themes.map((t, n) => {
        const name = resolveTheme(t.title);
        const row = cmp?.themes.find((r) => r.name === name);
        return <section key={t.title} className="panel theme-story">
          <aside>
            <span className="story-rank">{n + 1}</span>
            <h3><Link href={`/themes/${encodeURIComponent(name)}?week=${week}`}>{t.title}</Link></h3>
            {row && <p className="story-count">{row.current}건 <Delta row={row} /></p>}
            <TrendChart name={name} values={trendWeeks.map((w) => weekCount(w, name))} weeks={trendWeeks} />
          </aside>
          <div className="prose" dangerouslySetInnerHTML={{ __html: renderMarkdown(t.body).replace("<p><strong>근거 리포트", '<p class="sources"><strong>근거 리포트') }} />
        </section>;
      })}
    </>}

    {(industryFlow || dumbbell.length > 0) && <section className="panel industry-story">
      <div>
        <h2>산업 흐름</h2>
        <p className="legend"><span><i className="sw dot-prev" />지난주 같은 기간</span><span><i className="sw dot-cur" />이번 주</span></p>
        {dumbbell.length > 0 && <IndustryDumbbell rows={dumbbell} />}
      </div>
      {industryFlow && <div className="prose" dangerouslySetInnerHTML={{ __html: renderMarkdown(industryFlow) }} />}
    </section>}

    <nav className="week-nav" aria-label="다른 주">
      {neighbor(older, "older") ?? <span />}
      {neighbor(newer, "newer") ?? <span />}
    </nav>
    <ChartTooltip />
  </>;
}
