import Link from "next/link";
import { allReports, dashboardSnapshot } from "@/lib/data";
import { comparePeriods, weekLabel, weeklySeries } from "@/lib/dashboard";
import ChartTooltip from "@/components/charts/ChartTooltip";
import { WeekHeatmap } from "@/components/charts/WeekHeatmap";
import { Delta } from "@/components/dashboard/Delta";

export default function ThemesIndex() {
  const snapshot = dashboardSnapshot();
  const current = snapshot.weeks[0];
  if (!current) return <h1 className="page-title">테마</h1>;
  const cmp = comparePeriods(allReports(), current.week, current.throughDate);
  const { weeks, series } = weeklySeries(snapshot, "themes");
  const total = (v: number[]) => v.reduce((a, b) => a + b, 0);
  const row = (name: string) => cmp.themes.find((t) => t.name === name);
  // 이번 주 많이 다룬 순, 그다음 누적 순. 누적 2건 이상만 표에, 1건짜리는 따로
  const names = [...series.keys()].sort((a, b) => (series.get(b)!.at(-1)! - series.get(a)!.at(-1)!) || total(series.get(b)!) - total(series.get(a)!) || a.localeCompare(b, "ko"));
  const main = names.filter((n) => total(series.get(n)!) >= 2);
  const singles = names.filter((n) => total(series.get(n)!) < 2);
  const rising = cmp.themes.filter((t) => t.current >= 2 && (t.previous === 0 || t.delta > 0)).sort((a, b) => b.delta - a.delta).slice(0, 6);
  const fading = cmp.themes.filter((t) => t.previous >= 2 && t.delta < 0).sort((a, b) => a.delta - b.delta).slice(0, 6);
  const toRow = (n: string) => {
    const r = row(n);
    return { name: n, href: `/themes/${encodeURIComponent(n)}`, values: series.get(n)!, note: r && r.current > 0 ? <Delta row={r} /> : null };
  };

  return <>
    <p className="page-when">{weekLabel(current.week).label} · {current.throughDate}까지 집계 · 증감은 지난주 같은 기간 대비</p>
    <h1 className="page-title">테마</h1>
    <p className="sub">산업을 가로지르는 이슈가 주별로 언제 떠오르고 사그라드는지 봅니다.</p>

    <div className="split">
      <section className="panel">
        <h2>떠오르는 테마</h2>
        <p className="hint">이번 주 2건 이상, 지난주 같은 기간보다 늘었거나 새로 나온 테마</p>
        <ul className="hbars">{rising.map((t) => <li key={t.name}><Link className="hb-row" href={`/themes/${encodeURIComponent(t.name)}`}>
          <span className="hb-name">{t.name}</span><span className="hb-val" style={{ textAlign: "left" }}>{t.previous} → {t.current}건</span><Delta row={t} /></Link></li>)}</ul>
        {rising.length === 0 && <p className="sub">없음</p>}
      </section>
      <section className="panel">
        <h2>줄어든 테마</h2>
        <p className="hint">지난주 같은 기간 2건 이상이었는데 이번 주 줄어든 테마</p>
        <ul className="hbars">{fading.map((t) => <li key={t.name}><Link className="hb-row" href={`/themes/${encodeURIComponent(t.name)}`}>
          <span className="hb-name">{t.name}</span><span className="hb-val" style={{ textAlign: "left" }}>{t.previous} → {t.current}건</span><Delta row={t} /></Link></li>)}</ul>
        {fading.length === 0 && <p className="sub">없음</p>}
      </section>
    </div>

    <section className="panel">
      <h2>주별 테마 흐름</h2>
      <p className="hint">칸의 숫자는 그 주에 해당 테마를 다룬 개별 리포트 수입니다. 누적 2건 이상 테마 {main.length}개.</p>
      <WeekHeatmap rows={main.map(toRow)} weeks={weeks} noteLabel="이번 주" />
    </section>

    {singles.length > 0 && <details className="panel">
      <summary>한 번만 등장한 테마 {singles.length}개</summary>
      <p className="chips" style={{ marginTop: 12 }}>{singles.map((n) => <Link key={n} className="chip" href={`/themes/${encodeURIComponent(n)}`}>{n}</Link>)}</p>
    </details>}
    <ChartTooltip />
  </>;
}
