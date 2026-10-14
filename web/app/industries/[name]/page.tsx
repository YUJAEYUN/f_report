import Link from "next/link";
import { notFound } from "next/navigation";
import { allCards, countBy, dashboardSnapshot, decodeParam, industryBriefs, taxonomy } from "@/lib/data";
import { renderMarkdown } from "@/lib/md";
import { weekLabel, weeklySeries } from "@/lib/dashboard";
import ChartTooltip from "@/components/charts/ChartTooltip";
import { HBars } from "@/components/charts/HBars";
import { WeekBars } from "@/components/charts/WeekBars";
import { ReportList } from "@/components/ReportList";
import { EventList } from "@/components/EventList";
import { allEvents, industryRevisions, signalIndex, signedPct, stockHref, won } from "@/lib/signals";

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
  // 종목별 최신 투자의견·목표주가 (리포트 원문 + 이력표, scripts/signals.py)
  const stocks = signalIndex().stocks.filter((x) => x.industry === name && x.target_price != null)
    .sort((a, b) => (b.rating_date ?? "").localeCompare(a.rating_date ?? ""));
  const events = allEvents().filter((e) => e.industry === name).slice(0, 8);
  const rev = industryRevisions()[name] ?? {};
  const revWeeks = Object.keys(rev).sort().slice(-6);
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

    {(events.length > 0 || revWeeks.length > 0) && <div className="split">
      {revWeeks.length > 0 && <section className="panel">
        <h2>리비전 방향</h2>
        <p className="hint">주마다 목표주가·영업이익 추정을 올린 종목과 내린 종목 수</p>
        <ul className="rev-bars">{revWeeks.map((w) => {
          const v = rev[w];
          const max = Math.max(...revWeeks.map((k) => Math.max(rev[k].up, rev[k].down)), 1);
          return <li key={w}>
            <span className="rb-week">{weekLabel(w).label.replace("주차", "주")}</span>
            <span className="rb-down"><i style={{ width: `${(v.down / max) * 100}%` }} />{v.down ? v.down : ""}</span>
            <span className="rb-up"><i style={{ width: `${(v.up / max) * 100}%` }} />{v.up ? v.up : ""}</span>
            <span className="rb-n">관측 {v.stocks}</span>
          </li>;
        })}</ul>
        <p className="legend"><span><i className="sw" style={{ background: "var(--down)" }} />하향</span><span><i className="sw" style={{ background: "var(--up)" }} />상향</span></p>
      </section>}
      {events.length > 0 && <section className="panel">
        <h2>최근 숫자 변화</h2>
        <p className="hint"><Link href="/signals">전체 숫자 변화 →</Link></p>
        <EventList events={events} showDate compact />
      </section>}
    </div>}

    {stocks.length > 0 && <section className="panel">
      <h2>종목별 최근 의견</h2>
      <p className="hint">하나증권 리포트 원문과 투자의견 이력표 기준 · 최근 변경일 순</p>
      <div className="table-scroll">
        <table className="stock-table">
          <thead><tr><th>종목</th><th>투자의견</th><th className="num">목표주가</th><th className="num">최근 변경</th><th className="num">기준일</th></tr></thead>
          <tbody>{stocks.map((x) => <tr key={x.id}>
            <td><Link href={stockHref(x.id)!}>{x.name}</Link> <span className="muted">{x.code ?? ""}</span></td>
            <td>{x.rating ?? "-"}</td>
            <td className="num">{won(x.target_price)}</td>
            <td className={`num ${(x.last_tp_change?.pct ?? 0) > 0 ? "up" : (x.last_tp_change?.pct ?? 0) < 0 ? "down" : ""}`}>
              {x.last_tp_change ? `${signedPct(x.last_tp_change.pct)} (${x.last_tp_change.date.slice(2).replaceAll("-", ".")})` : "-"}</td>
            <td className="num">{x.rating_date?.slice(2).replaceAll("-", ".") ?? "-"}</td>
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
