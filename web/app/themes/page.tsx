import Link from "next/link";
import { dashboardSnapshot } from "@/lib/data";
import { themeChanges, weekLabel } from "@/lib/dashboard";

export default function ThemesIndex() {
  const snapshot = dashboardSnapshot();
  const week = snapshot.weeks[0];
  const changes = week ? themeChanges(snapshot, week.week).filter((c) => c.current > 0 && c.name !== "미분류") : [];
  return <>
    <div className="hero-head"><div><h1>테마 변화</h1></div>{week && <p className="asof">{weekLabel(week.week).label} · {week.throughDate}까지</p>}</div>
    <p className="sub">누적량이 아니라 이번 주와 직전 주를 같은 기준으로 비교합니다.</p>
    <div className="table-scroll" tabIndex={0}>
      <table className="compare-table"><thead><tr><th>테마</th><th>상태</th><th>전주</th><th>이번 주</th><th>증감</th><th>애널리스트</th><th>연결 산업</th></tr></thead>
      <tbody>{changes.map((c) => <tr key={c.name}><th><Link href={`/themes/${encodeURIComponent(c.name)}`}>{c.name}</Link></th><td><span className={`trend trend-${c.status}`}>{({new:"신규",up:"확대",steady:"지속",down:"약화",dropped:"미등장"})[c.status]}</span></td><td>{c.previous}</td><td><strong>{c.current}</strong></td><td>{c.delta > 0 ? "+" : ""}{c.delta}</td><td>{c.analystCount}명</td><td>{Object.entries(c.industries).sort((a,b)=>b[1]-a[1]).slice(0,3).map(([n])=>n).join(", ") || "-"}</td></tr>)}</tbody></table>
    </div>
  </>;
}
