import Link from "next/link";
import { notFound } from "next/navigation";
import { allCards, countBy, dashboardSnapshot, decodeParam, headlineOf, isoWeek, weeklyMarkdown, weeklyMeta } from "@/lib/data";
import { weekLabel, weeklySeries } from "@/lib/dashboard";
import ChartTooltip from "@/components/charts/ChartTooltip";
import { HBars } from "@/components/charts/HBars";
import { WeekBars } from "@/components/charts/WeekBars";
import { ReportList } from "@/components/ReportList";

export const dynamicParams = false;

export function generateStaticParams() {
  return countBy(allCards(), "themes").map(([name]) => ({ name }));
}

export default async function ThemePage({ params }: { params: Promise<{ name: string }> }) {
  const name = decodeParam((await params).name);
  const cards = allCards().filter((c) => c.themes.includes(name));
  if (cards.length === 0) notFound();
  const { weeks, series } = weeklySeries(dashboardSnapshot(), "themes");
  const values = series.get(name) ?? weeks.map(() => 0);
  const byWeek = new Map<string, typeof cards>();
  for (const c of cards) byWeek.set(isoWeek(c.date), [...(byWeek.get(isoWeek(c.date)) ?? []), c]);
  const individual = cards.filter((c) => c.type === "individual");
  const industries = countBy(individual, "industries").map(([n, v]) => ({ name: n, value: v, href: `/industries/${encodeURIComponent(n)}` }));
  const together = countBy(individual, "themes").filter(([n]) => n !== name).map(([n, v]) => ({ name: n, value: v, href: `/themes/${encodeURIComponent(n)}` }));
  const analysts = new Set(individual.map((c) => c.analyst).filter(Boolean)).size;
  const dates = cards.map((c) => c.date).sort();
  const featured = [...byWeek.keys()].filter((w) => weeklyMeta(w)?.themes.some((t) => t.name === name));

  return <>
    <p className="crumb"><Link href="/themes">테마</Link></p>
    <h1 className="page-title">{name}</h1>
    <p className="sub">리포트 {cards.length}건 · 애널리스트 {analysts}명 · {dates[0]} ~ {dates.at(-1)} · {byWeek.size}개 주에 등장</p>

    <div className="split">
      <section className="panel">
        <h2>주별 언급</h2>
        <p className="hint">이 테마를 다룬 개별 리포트 수 · 진한 막대가 이번 주</p>
        <WeekBars values={values} weeks={weeks} />
        {featured.length > 0 && <>
          <h2 className="sub-title">주간 인사이트에서 다룬 주</h2>
          <ul className="hbars">{featured.map((w) => <li key={w}><Link className="hb-row" style={{ gridTemplateColumns: "80px 1fr" }} href={`/weekly/${w}`}>
            <span className="hb-name">{weekLabel(w).label}</span><span>{headlineOf(weeklyMarkdown(w)).headline}</span></Link></li>)}</ul>
        </>}
      </section>
      <section className="panel">
        <h2>어느 산업 리포트에서 나왔나</h2>
        <HBars rows={industries} />
        {together.length > 0 && <>
          <h2 className="sub-title">함께 다뤄진 테마</h2>
          <HBars rows={together} limit={6} />
        </>}
      </section>
    </div>

    <div className="section-head"><h2>리포트</h2><span>최근 주부터</span></div>
    {[...byWeek.entries()].map(([week, list]) => (
      <section key={week} className="panel week-group">
        <h3>{weekLabel(week).label} <span>{weekLabel(week).range} · {list.length}건</span></h3>
        <ReportList cards={list} />
      </section>
    ))}
    <ChartTooltip />
  </>;
}
