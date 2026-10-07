import Link from "next/link";
import { notFound } from "next/navigation";
import { allCards, allReports, countBy, dashboardSnapshot, decodeParam, industryBriefs, taxonomy } from "@/lib/data";
import { renderMarkdown } from "@/lib/md";
import { weekLabel, weeklySeries } from "@/lib/dashboard";
import ChartTooltip from "@/components/charts/ChartTooltip";
import { HBars } from "@/components/charts/HBars";
import { WeekBars } from "@/components/charts/WeekBars";
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
  const { weeks, series } = weeklySeries(dashboardSnapshot(), "industries");
  const themes = countBy(cards, "themes").map(([n, v]) => ({ name: n, value: v, href: `/themes/${encodeURIComponent(n)}` }));
  // 종목별 가장 최근 투자의견·목표주가 (단일 종목 리포트만)
  const stocks = new Map<string, { ticker: string; title: string; id: string; date: string; rating?: string | null; tp?: number | string | null; change?: string | null }>();
  for (const r of allReports()) {
    const s = r.summary;
    if (r.report_type !== "individual" || !s?.ticker || !(r.industries ?? []).includes(name) || stocks.has(s.ticker)) continue;
    stocks.set(s.ticker, { ticker: s.ticker, title: r.title, id: r.report_id, date: r.published_date, rating: s.rating, tp: s.target_price, change: s.rating_change });
  }

  return <>
    <p className="crumb"><Link href="/industries">산업</Link></p>
    <h1 className="page-title">{name}</h1>
    <p className="sub">{taxonomy().industries[name]} · 리포트 {cards.length}건</p>

    <div className="split">
      <section className="panel">
        <h2>주별 리포트</h2>
        <p className="hint">이 산업을 다룬 개별 리포트 수 · 진한 막대가 이번 주</p>
        <WeekBars values={series.get(name) ?? weeks.map(() => 0)} weeks={weeks} />
      </section>
      <section className="panel">
        <h2>이 산업에서 다룬 테마</h2>
        <HBars rows={themes} />
      </section>
    </div>

    {stocks.size > 0 && <section className="panel">
      <h2>종목별 최근 의견</h2>
      <p className="hint">단일 종목 리포트 기준, 종목마다 가장 최근 리포트</p>
      <div className="table-scroll">
        <table className="stock-table">
          <thead><tr><th>종목</th><th>리포트</th><th>투자의견</th><th className="num">목표주가</th><th className="num">발행일</th></tr></thead>
          <tbody>{[...stocks.values()].map((s) => <tr key={s.ticker}>
            <td>{s.ticker}</td>
            <td><Link href={`/reports/${s.id}`}>{s.title}</Link></td>
            <td>{s.rating ?? "-"}{s.change && s.change !== "유지" ? ` (${s.change})` : ""}</td>
            <td className="num">{s.tp != null && s.tp !== "" ? Number(s.tp).toLocaleString("ko-KR") : "-"}</td>
            <td className="num">{s.date.slice(5).replace("-", ".")}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </section>}

    {briefs.length > 0 && <div className="section-head"><h2>주간 브리핑</h2><span>최근 주부터</span></div>}
    {briefs.map((b) => (
      <details key={b.week} id={b.week} className="panel" open={b === briefs[0]}>
        <summary><strong>{weekLabel(b.week).label} 브리핑</strong> <span className="count">{weekLabel(b.week).range}</span></summary>
        <div className="prose" dangerouslySetInnerHTML={{ __html: renderMarkdown(b.markdown, { dropTitle: true }) }} />
      </details>
    ))}

    <section className="panel">
      <h2>리포트</h2>
      <ReportList cards={cards} />
    </section>
    <ChartTooltip />
  </>;
}
