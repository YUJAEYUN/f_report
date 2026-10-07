import Link from "next/link";
import { weekLabel } from "@/lib/dashboard";
import { dashboardSnapshot, taxonomy } from "@/lib/data";

export default function IndustriesIndex() {
  const snapshot = dashboardSnapshot();
  const current = snapshot.weeks[0]; const previous = snapshot.weeks[1];
  const now = new Map(current?.industries.map((i) => [i.name, i])); const before = new Map(previous?.industries.map((i) => [i.name, i.count]));
  return <>
    <div className="hero-head"><div><h1>산업 관심도</h1></div>{current && <p className="asof">{weekLabel(current.week).label} · {current.throughDate}까지</p>}</div>
    <p className="sub">리포트가 주제로 다룬 횟수입니다. 산업 전망이나 투자 매력도를 뜻하지 않습니다.</p>
    <div className="industry-grid">{Object.entries(taxonomy().industries).map(([name, desc]) => {
      const stat = now.get(name); const count = stat?.count ?? 0; const prev = before.get(name) ?? 0; const delta = count - prev;
      return <Link className={`industry-card ${count ? "" : "is-empty"}`} href={count ? `/industries/${encodeURIComponent(name)}` : "#"} key={name} aria-disabled={!count}>
        <div><strong>{name}</strong><span>{desc}</span></div><div className="industry-metric"><strong>{count}</strong><span className={delta > 0 ? "positive" : ""}>{delta > 0 ? "+" : ""}{delta}</span></div>
      </Link>;
    })}</div>
  </>;
}
