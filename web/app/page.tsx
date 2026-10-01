import Link from "next/link";
import { allCards, dashboardSnapshot, digestDates, digestMarkdown, section, weeklyMarkdown, weeklyMeta, weeks } from "@/lib/data";
import { themeChanges, themeIndustryMatrix } from "@/lib/dashboard";
import { renderMarkdown } from "@/lib/md";
import { ReportList } from "@/components/ReportList";
import { DataStatus } from "@/components/dashboard/DataStatus";
import { ThemeChangeList } from "@/components/dashboard/ThemeChangeList";
import { ThemeIndustryHeatmap } from "@/components/dashboard/ThemeIndustryHeatmap";

export default function Home() {
  const week = weeks()[0];
  const weeklyMd = week ? weeklyMarkdown(week) : null;
  const meta = week ? weeklyMeta(week) : null;
  const glance = weeklyMd ? section(weeklyMd, /한눈에/) : null;
  const cards = allCards();
  const date = digestDates().find((d) => cards.some((c) => c.date === d && c.type === "individual"));
  const digestMd = date ? digestMarkdown(date) : null;
  const today = digestMd ? section(digestMd, /핵심/) : null;
  const recent = cards.filter((c) => c.type === "individual").slice(0, 8);
  const snapshot = dashboardSnapshot();
  const selectedWeek = snapshot.weeks[0];
  const changes = selectedWeek ? themeChanges(snapshot, selectedWeek.week) : [];
  const matrix = selectedWeek ? themeIndustryMatrix(snapshot, selectedWeek.week) : [];
  const heatThemes = changes.filter((c) => c.current > 0 && c.name !== "미분류").slice(0, 5).map((c) => c.name);
  const heatIndustries = selectedWeek?.industries.filter((i) => i.name !== "미분류").slice(0, 8).map((i) => i.name) ?? [];

  return <>
    <div className="hero-head">
      <div><p className="eyebrow">RESEARCH MONITOR</p><h1>이번 주, 무엇이 달라졌나</h1></div>
      {selectedWeek && <p className="asof">{selectedWeek.week} · {selectedWeek.throughDate}까지 집계</p>}
    </div>
    <DataStatus snapshot={snapshot} />

    {selectedWeek && <section className="card dashboard-card">
      <div className="card-head"><div><p className="eyebrow">WEEKLY CHANGE</p><h2>주목할 변화</h2></div><Link href={`/weekly/${selectedWeek.week}`}>전체 변화 보기 →</Link></div>
      <p className="sub">개별 리포트 언급량 기준 · 직전 ISO 주 대비</p>
      <ThemeChangeList changes={changes} week={selectedWeek.week} limit={5} />
    </section>}

    {week && <section className="card dashboard-card summary-card">
      <div className="card-head"><div><p className="eyebrow">WEEKLY BRIEF</p><h2>이번 주 한눈에</h2></div><Link href={`/weekly/${week}`}>전체 인사이트 →</Link></div>
      {glance && <div className="prose clamp-summary" dangerouslySetInnerHTML={{ __html: renderMarkdown(glance) }} />}
      {meta && <div className="chips">{meta.themes.slice(0, 5).map((t) => <Link key={t.name} className="chip theme" href={`/themes/${encodeURIComponent(t.name)}`}>{t.name}<span className="n">{t.report_ids.length}</span></Link>)}</div>}
    </section>}

    {selectedWeek && heatThemes.length > 0 && heatIndustries.length > 0 && <section className="card dashboard-card">
      <div className="card-head"><div><p className="eyebrow">CONNECTIONS</p><h2>테마 × 산업 관계</h2></div><Link href="/themes">테마 탐색 →</Link></div>
      <p className="sub">같은 리포트에서 함께 다뤄진 횟수입니다. 투자 방향이나 인과관계를 뜻하지 않습니다.</p>
      <ThemeIndustryHeatmap cells={matrix} week={selectedWeek.week} themes={heatThemes} industries={heatIndustries} />
    </section>}

    <div className="grid2 dashboard-bottom">
      {date && <section className="card"><div className="card-head"><h2>최근 발행일 · {date}</h2><Link href={`/daily/${date}`}>다이제스트 →</Link></div>{today && <div className="prose compact-prose" dangerouslySetInnerHTML={{ __html: renderMarkdown(today) }} />}</section>}
      <section className="card"><div className="card-head"><h2>최근 리포트</h2><Link href="/reports">전체 보기 →</Link></div><ReportList cards={recent} /></section>
    </div>
  </>;
}
