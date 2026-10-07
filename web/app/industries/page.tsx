import { allReports, dashboardSnapshot, taxonomy } from "@/lib/data";
import { comparePeriods, weekLabel, weeklySeries } from "@/lib/dashboard";
import ChartTooltip from "@/components/charts/ChartTooltip";
import { IndustryDumbbell } from "@/components/charts/IndustryDumbbell";
import { WeekHeatmap } from "@/components/charts/WeekHeatmap";
import { Delta } from "@/components/dashboard/Delta";

export default function IndustriesIndex() {
  const snapshot = dashboardSnapshot();
  const current = snapshot.weeks[0];
  if (!current) return <h1 className="page-title">산업</h1>;
  const cmp = comparePeriods(allReports(), current.week, current.throughDate);
  const { weeks, series } = weeklySeries(snapshot, "industries");
  const total = (v: number[]) => v.reduce((a, b) => a + b, 0);
  const names = Object.keys(taxonomy().industries).filter((n) => series.has(n))
    .sort((a, b) => (series.get(b)!.at(-1)! - series.get(a)!.at(-1)!) || total(series.get(b)!) - total(series.get(a)!));
  const quiet = Object.keys(taxonomy().industries).filter((n) => !series.has(n));
  const dumbbell = cmp.industries.filter((r) => r.current > 0 || r.previous > 0).slice(0, 12);

  return <>
    <p className="page-when">{weekLabel(current.week).label} · {current.throughDate}까지 집계 · 증감은 지난주 같은 기간 대비</p>
    <h1 className="page-title">산업</h1>
    <p className="sub">리포트가 주제로 다룬 건수입니다. 산업 전망이나 투자 매력도를 뜻하지 않습니다.</p>

    <div className="split">
      <section className="panel">
        <h2>이번 주 산업 관심도</h2>
        <p className="legend"><span><i className="sw dot-prev" />지난주 같은 기간</span><span><i className="sw dot-cur" />이번 주</span></p>
        <IndustryDumbbell rows={dumbbell} />
      </section>
      <section className="panel">
        <h2>주별 산업 흐름</h2>
        <p className="hint">칸의 숫자는 그 주에 해당 산업을 다룬 개별 리포트 수입니다.</p>
        <WeekHeatmap weeks={weeks} noteLabel="이번 주" rows={names.map((n) => {
          const r = cmp.industries.find((x) => x.name === n);
          return { name: n, href: `/industries/${encodeURIComponent(n)}`, values: series.get(n)!, note: r && r.current > 0 ? <Delta row={r} /> : null };
        })} />
        {quiet.length > 0 && <p className="hint" style={{ marginTop: 12 }}>아직 리포트가 없는 산업: {quiet.join(", ")}</p>}
      </section>
    </div>
    <ChartTooltip />
  </>;
}
