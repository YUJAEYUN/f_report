import Link from "next/link";
import { notFound } from "next/navigation";
import { allCards, decodeParam, digestDates, digestMarkdown, section } from "@/lib/data";
import { isoWeek, weekLabel } from "@/lib/dashboard";
import { renderMarkdown, withReportTitles } from "@/lib/md";
import { eventsOn } from "@/lib/signals";
import { EventList } from "@/components/EventList";

export const dynamicParams = false;

export function generateStaticParams() {
  return digestDates().map((date) => ({ date }));
}

const WD = ["일", "월", "화", "수", "목", "금", "토"];

export default async function DailyPage({ params }: { params: Promise<{ date: string }> }) {
  const date = decodeParam((await params).date);
  const md = digestMarkdown(date);
  if (!md) notFound();
  const all = digestDates();
  const i = all.indexOf(date);
  const newer = i > 0 ? all[i - 1] : null;
  const older = i < all.length - 1 ? all[i + 1] : null;
  const cards = allCards().filter((c) => c.date === date);
  const individual = cards.filter((c) => c.type === "individual");
  const titles = new Map(allCards().map((c) => [c.id, c.title]));
  const html = (m: string | null) => (m ? withReportTitles(renderMarkdown(m), titles) : "");
  const d = new Date(`${date}T00:00:00Z`);
  const week = isoWeek(date);

  const headline = section(md, /오늘 한 줄/);
  const core = section(md, /핵심/);
  const terms = section(md, /용어/);
  const dailyComment = section(md, /데일리 코멘트/);
  const briefs = section(md, /산업별 브리핑/);
  const events = eventsOn(date);
  const isNew = !!headline; // 쉬운 말 형식 이전의 다이제스트는 원문 그대로 보여준다

  return <>
    <p className="page-when">
      <span>일간 다이제스트 · {d.getUTCMonth() + 1}월 {d.getUTCDate()}일 ({WD[d.getUTCDay()]}) · 개별 리포트 {individual.length}건 · <Link href={`/weekly/${week}`}>{weekLabel(week).label}</Link></span>
      <span className="week-jump">
        {older && <Link href={`/daily/${older}`}>← {older.slice(5).replace("-", ".")}</Link>}
        {newer && <Link href={`/daily/${newer}`}>{newer.slice(5).replace("-", ".")} →</Link>}
      </span>
    </p>

    {isNew ? <>
      <div className="map-hero daily-hero">
        <section className="panel">
          <h2>오늘 한 줄</h2>
          <h1 className="headline">{headline!.replace(/^[-*>\s]+/, "")}</h1>
          {core && <div className="prose core" dangerouslySetInnerHTML={{ __html: html(core) }} />}
        </section>
        {terms && <section className="panel">
          <h2>용어 풀이</h2>
          <p className="hint">오늘 다이제스트에 나온 말</p>
          <div className="prose terms" dangerouslySetInnerHTML={{ __html: html(terms).replace(/<\/strong>\s*[:：]\s*/g, "</strong>") }} />
        </section>}
      </div>
      {events.length > 0 && <section className="panel">
        <div className="review-head"><h2>숫자 변화 {events.length}건</h2><Link href="/signals" className="more">전체 →</Link></div>
        <p className="hint">목표주가·투자의견·실적 추정치·컨센서스가 크게 바뀐 종목</p>
        <EventList events={events} />
      </section>}
      {(dailyComment || briefs) && <div className="split">
        {dailyComment && <section className="panel">
          <h2>데일리 코멘트</h2>
          <div className="prose compact" dangerouslySetInnerHTML={{ __html: html(dailyComment) }} />
        </section>}
        {briefs && <section className="panel">
          <h2>산업별 브리핑 업데이트</h2>
          <div className="prose compact" dangerouslySetInnerHTML={{ __html: html(briefs) }} />
        </section>}
      </div>}
    </> : <article className="panel prose" dangerouslySetInnerHTML={{ __html: withReportTitles(renderMarkdown(md, { dropTitle: true }), titles) }} />}

    {individual.length > 0 && <>
      <div className="section-head"><h2>이 날 올라온 개별 리포트 {individual.length}건</h2><Link href="/reports">전체 리포트 →</Link></div>
      <div className="report-cards">
        {individual.map((c) => <Link key={c.id} href={`/reports/${c.id}`} className="report-card">
          <span className="rc-meta">{c.broker ? `${c.broker} · ` : ""}{c.analyst ?? ""}{c.industries.length ? ` · ${c.industries.join(", ")}` : ""}</span>
          <b>{c.title}</b>
          <span className="rc-one">{c.oneLiner}</span>
          {c.badge && <span className="rc-badge">{c.badge}</span>}
        </Link>)}
      </div>
    </>}
  </>;
}
