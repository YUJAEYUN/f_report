import Link from "next/link";
import { allCards, allReports, dashboardSnapshot, digestDates, digestMarkdown, section, weeklyMarkdown, weeks } from "@/lib/data";
import { comparePeriods, themeIndustryMatrix, weekLabel } from "@/lib/dashboard";
import { renderMarkdown } from "@/lib/md";
import { ReportList } from "@/components/ReportList";
import { Delta, RankBars } from "@/components/dashboard/RankBars";
import { ThemeIndustryHeatmap } from "@/components/dashboard/ThemeIndustryHeatmap";

export default function Home() {
  const snapshot = dashboardSnapshot();
  const current = snapshot.weeks[0];
  const cards = allCards();
  const recent = cards.filter((c) => c.type === "individual").slice(0, 6);
  const digestDate = digestDates().find((d) => cards.some((c) => c.date === d && c.type === "individual"));
  const today = digestDate ? section(digestMarkdown(digestDate) ?? "", /핵심/) : null;

  if (!current) {
    return <>
      <h1>리서치 트래커</h1>
      <p className="sub">아직 집계된 리포트가 없습니다.</p>
    </>;
  }

  const wl = weekLabel(current.week);
  const cmp = comparePeriods(allReports(), current.week, current.throughDate);
  const weeklyMd = weeks().includes(current.week) ? weeklyMarkdown(current.week) : null;
  const glance = weeklyMd ? section(weeklyMd, /한눈에/) : null;
  const topTheme = cmp.themes.find((t) => t.current > 0);
  const topIndustry = cmp.industries.find((i) => i.current > 0);
  // "많이 다룬 테마"에 이미 나온 테마는 빼고, 그 아래에서 커지는 흐름을 보여준다
  const topNames = new Set(cmp.themes.filter((t) => t.current > 0).slice(0, 6).map((t) => t.name));
  const rising = cmp.themes.filter((t) => !topNames.has(t.name) && t.current >= 2 && (t.previous === 0 || t.delta > 0))
    .sort((a, b) => b.delta - a.delta || b.current - a.current);
  const fading = cmp.themes.filter((t) => t.previous >= 2 && t.delta < 0).sort((a, b) => a.delta - b.delta);
  // 1건짜리 신규 테마는 이름만 다른 일회성인 경우가 많아 2건 이상만 센다
  const newThemes = cmp.themes.filter((t) => t.current >= 2 && t.previous === 0);
  const heatThemes = cmp.themes.filter((t) => t.current > 0).slice(0, 5).map((t) => t.name);
  const heatIndustries = cmp.industries.filter((i) => i.current > 0).slice(0, 8).map((i) => i.name);
  const reportDelta = cmp.reports.current - cmp.reports.previous;
  const themeHref = (name: string) => `/themes/${encodeURIComponent(name)}?week=${current.week}`;

  return <>
    <div className="hero-head">
      <div><p className="eyebrow">RESEARCH MONITOR · {wl.label}</p><h1>이번 주, 무엇이 달라졌나</h1></div>
      <p className="asof">{wl.range} · {current.throughDate}까지 집계</p>
    </div>

    <section className="kpi-grid" aria-label="이번 주 핵심 지표">
      <div className="kpi">
        <span>이번 주 개별 리포트</span>
        <strong>{cmp.reports.current}건</strong>
        <em className={reportDelta > 0 ? "is-up" : reportDelta < 0 ? "is-down" : ""}>
          지난주 같은 기간 {cmp.reports.previous}건
        </em>
      </div>
      {topTheme && <Link className="kpi" href={themeHref(topTheme.name)}>
        <span>가장 많이 다룬 테마</span>
        <strong>{topTheme.name}</strong>
        <em>{topTheme.current}건 · <Delta row={topTheme} /></em>
      </Link>}
      {topIndustry && <Link className="kpi" href={`/industries/${encodeURIComponent(topIndustry.name)}`}>
        <span>가장 많이 다룬 산업</span>
        <strong>{topIndustry.name}</strong>
        <em>{topIndustry.current}건 · <Delta row={topIndustry} /></em>
      </Link>}
      <div className="kpi">
        <span>새로 등장한 테마 (2건 이상)</span>
        <strong>{newThemes.length}개</strong>
        <em>{newThemes.map((t) => t.name).slice(0, 2).join(" · ") || "없음"}</em>
      </div>
    </section>

    {glance && <section className="card dashboard-card summary-card">
      <div className="card-head"><div><p className="eyebrow">WEEKLY BRIEF</p><h2>이번 주 한눈에</h2></div><Link href={`/weekly/${current.week}`}>주간 인사이트 전체 →</Link></div>
      <div className="prose clamp-summary" dangerouslySetInnerHTML={{ __html: renderMarkdown(glance) }} />
    </section>}

    <div className="grid2">
      <section className="card dashboard-card">
        <div className="card-head"><div><p className="eyebrow">THEMES</p><h2>많이 다룬 테마</h2></div><Link href="/themes">테마 전체 →</Link></div>
        <p className="sub">개별 리포트 언급 건수 · 증감은 지난주 같은 기간({cmp.previousThrough}까지) 대비</p>
        <RankBars rows={cmp.themes} hrefFor={themeHref} />
      </section>
      <section className="card dashboard-card">
        <div className="card-head"><div><p className="eyebrow">INDUSTRIES</p><h2>산업 관심도</h2></div><Link href="/industries">산업 전체 →</Link></div>
        <p className="sub">리포트가 주제로 다룬 건수입니다. 전망이나 투자 매력도를 뜻하지 않습니다.</p>
        <RankBars rows={cmp.industries} hrefFor={(n) => `/industries/${encodeURIComponent(n)}`} />
      </section>
    </div>

    <div className="grid2">
      <section className="card dashboard-card">
        <div className="card-head"><div><p className="eyebrow">MOMENTUM</p><h2>떠오르는 테마</h2></div><Link href={`/weekly/${current.week}`}>전체 변화 →</Link></div>
        <p className="sub">위 상위 테마 밖에서 지난주 같은 기간보다 언급이 늘었거나 새로 나온 테마 (2건 이상)</p>
        <RankBars rows={rising} hrefFor={themeHref} limit={5} />
        {fading.length > 0 && <>
          <h3 className="mini-head">줄어든 테마</h3>
          <p className="chips">{fading.slice(0, 4).map((t) => (
            <Link key={t.name} className="chip" href={themeHref(t.name)}>{t.name}<span className="n">{t.previous}→{t.current}</span></Link>
          ))}</p>
        </>}
      </section>
      {digestDate && today && <section className="card dashboard-card">
        <div className="card-head"><div><p className="eyebrow">LATEST DAY</p><h2>최근 발행일 핵심 · {digestDate}</h2></div><Link href={`/daily/${digestDate}`}>다이제스트 →</Link></div>
        <div className="prose compact-prose" dangerouslySetInnerHTML={{ __html: renderMarkdown(today) }} />
        <p className="more-link"><Link href="/daily">지난 일간 다이제스트 →</Link></p>
      </section>}
    </div>

    {heatThemes.length > 0 && heatIndustries.length > 0 && <section className="card dashboard-card">
      <div className="card-head"><div><p className="eyebrow">CONNECTIONS</p><h2>테마 × 산업</h2></div></div>
      <p className="sub">많이 다룬 테마가 어느 산업 리포트에서 나왔는지 · 같은 리포트에서 함께 다뤄진 건수이며 인과관계를 뜻하지 않습니다.</p>
      <ThemeIndustryHeatmap cells={themeIndustryMatrix(snapshot, current.week)} week={current.week} themes={heatThemes} industries={heatIndustries} />
    </section>}

    <section className="card">
      <div className="card-head"><h2>최근 리포트</h2><Link href="/reports">전체 보기 →</Link></div>
      <ReportList cards={recent} />
    </section>

  </>;
}
