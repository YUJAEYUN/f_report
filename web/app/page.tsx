import Link from "next/link";
import { allCards, allReports, dashboardSnapshot, digestDates, headlineOf, weeklyMarkdown, weeks } from "@/lib/data";
import { comparePeriods, themeIndustryMatrix, weekdayCounts, weekLabel } from "@/lib/dashboard";
import ChartTooltip from "@/components/charts/ChartTooltip";
import { DailyVolume } from "@/components/charts/DailyVolume";
import { IndustryDumbbell } from "@/components/charts/IndustryDumbbell";
import { ThemeTreemap } from "@/components/charts/ThemeTreemap";
import { ThemeTrends } from "@/components/charts/ThemeTrends";
import { Delta } from "@/components/dashboard/Delta";
import { ThemeIndustryHeatmap } from "@/components/dashboard/ThemeIndustryHeatmap";

export default function Home() {
  const snapshot = dashboardSnapshot();
  const current = snapshot.weeks[0];
  const cards = allCards();
  if (!current) return <><h1>리서치 맵</h1><p className="sub">아직 집계된 리포트가 없습니다.</p></>;

  const reports = allReports();
  const wl = weekLabel(current.week);
  const cmp = comparePeriods(reports, current.week, current.throughDate);
  const { headline, lead } = headlineOf(weeks().includes(current.week) ? weeklyMarkdown(current.week) : null);
  const reportDelta = cmp.reports.current - cmp.reports.previous;
  const mapRows = cmp.themes.filter((t) => t.current >= 2).slice(0, 16);
  const singles = cmp.themes.filter((t) => t.current === 1).length;
  const newThemes = cmp.themes.filter((t) => t.current >= 2 && t.previous === 0).length;
  const volume = weekdayCounts(reports, current.week, current.throughDate);

  // 최근 4주 추이: 스냅샷은 주 전체 집계라 이번 주 값은 진행 중인 주까지의 값이다
  const trendWeeks = snapshot.weeks.slice(0, 4).map((w) => w.week).reverse();
  const weekCount = (week: string, name: string) => snapshot.weeks.find((w) => w.week === week)?.themes.find((t) => t.name === name)?.count ?? 0;
  const topThemes = cmp.themes.filter((t) => t.current > 0).slice(0, 6);
  const trends = topThemes.map((t) => ({ name: t.name, values: trendWeeks.map((w) => weekCount(w, t.name)), badge: <>{t.current}건 <Delta row={t} /></> }));
  const dumbbell = cmp.industries.filter((i) => i.current > 0 || i.previous > 0).slice(0, 9);
  const heatThemes = topThemes.map((t) => t.name);
  const heatIndustries = cmp.industries.filter((i) => i.current > 0).slice(0, 7).map((i) => i.name);
  const recent = cards.filter((c) => c.type === "individual").slice(0, 6);
  const byId = new Map(reports.map((r) => [r.report_id, r]));
  const digestDate = digestDates().find((d) => cards.some((c) => c.date === d && c.type === "individual"));

  return <>
    <p className="page-when">{wl.label} · {wl.range} · {current.throughDate}까지 집계</p>

    <div className="map-hero">
      <section className="panel">
        <h2>{wl.label} 테마 지도</h2>
        <p className="hint">면적은 이번 주 언급 건수, 색은 지난주 같은 기간 대비 변화입니다. 빨강 증가 · 파랑 감소 · 진한 빨강 신규. 2건 이상 테마만, 1건짜리 {singles}개는 제외.</p>
        <ThemeTreemap rows={mapRows} week={current.week} />
      </section>

      <section className="panel">
        <h2>이번 주 한 줄</h2>
        {headline && <h1 className="headline">{headline}</h1>}
        {lead && <p className="lead">{lead.length > 170 ? `${lead.slice(0, 170)}…` : lead} <Link href={`/weekly/${current.week}`}>주간 인사이트 →</Link></p>}
        <div className="big-numbers">
          <div><span>개별 리포트</span><strong>{cmp.reports.current}</strong>
            {reportDelta !== 0 && <em className={reportDelta > 0 ? "up" : "down"}>{reportDelta > 0 ? "▲" : "▼"}{Math.abs(reportDelta)}</em>}</div>
          <div><span>테마 (2건 이상)</span><strong>{mapRows.length}</strong></div>
          <div><span>신규 테마</span><strong>{newThemes}</strong></div>
        </div>
        <h2 className="sub-title">요일별 발행</h2>
        <p className="legend"><span><i className="sw vol-prev" />지난주</span><span><i className="sw vol-cur" />이번 주</span></p>
        <DailyVolume current={volume.current} previous={volume.previous} />
      </section>
    </div>

    <div className="map-row">
      <section className="panel">
        <h2>상위 테마 흐름</h2>
        <p className="hint">최근 {trendWeeks.length}주 주별 언급 건수 · 이번 주는 {current.throughDate}까지</p>
        <ThemeTrends items={trends} weeks={trendWeeks} />
      </section>
      <section className="panel">
        <h2>산업 관심도 변화</h2>
        <p className="legend"><span><i className="sw dot-prev" />지난주 같은 기간</span><span><i className="sw dot-cur" />이번 주</span></p>
        <IndustryDumbbell rows={dumbbell} />
      </section>
    </div>

    {heatThemes.length > 0 && heatIndustries.length > 0 && <section className="panel">
      <h2>테마는 어느 산업에서 나왔나</h2>
      <p className="hint">상위 테마 × 상위 산업 · 같은 리포트에서 함께 다뤄진 건수</p>
      <ThemeIndustryHeatmap cells={themeIndustryMatrix(snapshot, current.week)} week={current.week} themes={heatThemes} industries={heatIndustries} />
    </section>}

    <div className="section-head"><h2>최근 리포트</h2>
      <span>{digestDate && <Link href={`/daily/${digestDate}`}>{digestDate} 다이제스트</Link>} · <Link href="/reports">전체 리포트 →</Link></span></div>
    <div className="report-cards">
      {recent.map((c) => {
        const s = byId.get(c.id)?.summary;
        const badge = [s?.rating, s?.target_price ? `TP ${Number(s.target_price).toLocaleString("ko-KR")}` : null].filter(Boolean).join(" · ");
        return <Link key={c.id} href={`/reports/${c.id}`} className="report-card">
          <span className="rc-meta">{c.date.slice(5).replace("-", ".")} · {c.analyst ?? ""}{c.industries.length ? ` · ${c.industries.join(", ")}` : ""}</span>
          <b>{c.title}</b>
          <span className="rc-one">{c.oneLiner}</span>
          {badge && <span className="rc-badge">{badge}</span>}
        </Link>;
      })}
    </div>
    <ChartTooltip />
  </>;
}
