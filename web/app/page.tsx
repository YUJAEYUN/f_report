import Link from "next/link";
import { allCards, digestDates, digestMarkdown, section, weeklyMarkdown, weeklyMeta, weeks } from "@/lib/data";
import { renderMarkdown } from "@/lib/md";
import { ReportList } from "@/components/ReportList";

export default function Home() {
  const week = weeks()[0];
  const weeklyMd = week ? weeklyMarkdown(week) : null;
  const meta = week ? weeklyMeta(week) : null;
  const glance = weeklyMd ? section(weeklyMd, /한눈에/) : null;

  const cards = allCards();
  // 데일리 코멘트만 있는 날(휴일 전후 등)은 건너뛰고, 개별 리포트가 있었던 최근 날을 보여준다
  const date = digestDates().find((d) => cards.some((c) => c.date === d && c.type === "individual"));
  const digestMd = date ? digestMarkdown(date) : null;
  const today = digestMd ? section(digestMd, /핵심/) : null;

  const recent = cards.filter((c) => c.type === "individual").slice(0, 12);

  return (
    <>
      {week && (
        <section className="card">
          <div className="card-head">
            <h2>이번 주 · {week}</h2>
            <Link href={`/weekly/${week}`}>주간 인사이트 전체 →</Link>
          </div>
          {glance && <div className="prose" dangerouslySetInnerHTML={{ __html: renderMarkdown(glance) }} />}
          {meta && meta.themes.length > 0 && (
            <div className="chips">
              {meta.themes.map((t) => (
                <Link key={t.name} className="chip theme" href={`/themes/${encodeURIComponent(t.name)}`}>
                  {t.name}<span className="n">{t.report_ids.length}</span>
                </Link>
              ))}
            </div>
          )}
        </section>
      )}

      {date && (
        <section className="card">
          <div className="card-head">
            <h2>최근 발행일 · {date}</h2>
            <Link href={`/daily/${date}`}>일간 다이제스트 →</Link>
          </div>
          {today && <div className="prose" dangerouslySetInnerHTML={{ __html: renderMarkdown(today) }} />}
        </section>
      )}

      <section className="card">
        <div className="card-head">
          <h2>최근 리포트</h2>
          <Link href="/reports">전체 보기 →</Link>
        </div>
        <ReportList cards={recent} />
      </section>
    </>
  );
}
