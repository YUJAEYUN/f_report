import Link from "next/link";
import { weekLabel } from "@/lib/dashboard";
import { allEvents, industryRevisions, signalIndex, signedPct, stockHref, won } from "@/lib/signals";
import { EventList } from "@/components/EventList";
import ChartTooltip from "@/components/charts/ChartTooltip";

const TYPE_GROUPS: { label: string; types: string[] }[] = [
  { label: "목표주가", types: ["tp_up", "tp_down", "tp_streak", "tp_accel"] },
  { label: "투자의견", types: ["rating_up", "rating_down", "coverage_start", "coverage_end"] },
  { label: "추정치", types: ["est_up", "est_down", "est_turn"] },
  { label: "컨센서스", types: ["cons_up", "cons_down", "cons_turn", "gap_above", "gap_below"] },
];

export default function SignalsPage() {
  const events = allEvents();
  const { window_start, stocks } = signalIndex();
  const dates = [...new Set(events.map((e) => e.date))];
  const recentDates = dates.slice(0, 10);
  const revisions = industryRevisions();
  const weeks = [...new Set(Object.values(revisions).flatMap((w) => Object.keys(w)))].sort().slice(-5);
  const industries = Object.entries(revisions)
    .filter(([, w]) => weeks.some((k) => w[k] && (w[k].up || w[k].down)))
    .sort((a, b) => a[0].localeCompare(b[0], "ko"));
  const movers = stocks.filter((s) => s.last_tp_change && window_start && s.last_tp_change.date >= window_start)
    .sort((a, b) => Math.abs(b.last_tp_change!.pct) - Math.abs(a.last_tp_change!.pct)).slice(0, 12);
  const counts = TYPE_GROUPS.map((g) => ({ ...g, n: events.filter((e) => g.types.includes(e.type)).length }));

  return <>
    <h1 className="page-title">숫자 변화</h1>
    <p className="sub">리포트 속 투자의견·목표주가·실적 추정치·컨센서스를 코드로 읽어 종목별로 쌓고, 방향과 속도가 크게 바뀐 지점을 이벤트로 표시합니다. {window_start} 이후 · 하나증권 리포트 기준.</p>

    <div className="big-numbers signal-numbers">
      {counts.map((c) => <div key={c.label}><span>{c.label} 이벤트</span><strong>{c.n}</strong></div>)}
    </div>

    <div className="report-layout signals-layout">
      <article className="report-main">
        {recentDates.map((d) => <section key={d} className="panel">
          <h2><Link href={`/daily/${d}`}>{d.slice(5).replace("-", "월 ")}일</Link></h2>
          <EventList events={events.filter((e) => e.date === d)} />
        </section>)}
        {dates.length === 0 && <section className="panel"><p className="sub" style={{ margin: 0 }}>아직 이벤트가 없습니다.</p></section>}
      </article>

      <aside className="report-side">
        {industries.length > 0 && <section className="panel">
          <h2>산업별 리비전 방향</h2>
          <p className="hint">주마다 목표주가·영업이익 추정을 올린 종목(▲)과 내린 종목(▼) 수. 색은 (상향−하향)/관측 종목 수.</p>
          <div className="rev-grid" style={{ ["--n" as string]: weeks.length }}>
            <span />
            {weeks.map((w) => <span key={w} className="rev-head">{weekLabel(w).label.replace("주차", "주")}</span>)}
            {industries.map(([ind, w]) => <div key={ind} className="rev-row">
              <Link href={`/industries/${encodeURIComponent(ind)}`} className="rev-name">{ind}</Link>
              {weeks.map((k) => {
                const v = w[k];
                if (!v) return <span key={k} className="rev-cell is-empty" />;
                const bg = v.ratio > 0 ? `color-mix(in srgb, var(--up) ${Math.round(v.ratio * 70)}%, var(--cell))`
                  : v.ratio < 0 ? `color-mix(in srgb, var(--down) ${Math.round(-v.ratio * 70)}%, var(--cell))` : "var(--cell)";
                return <span key={k} className="rev-cell" style={{ background: bg }}
                  data-tip={`${ind} · ${weekLabel(k).label} · 상향 ${v.up} · 하향 ${v.down} · 변화 없음 ${v.flat}`}>
                  {v.up || v.down ? <>{v.up ? `▲${v.up}` : ""}{v.down ? `▼${v.down}` : ""}</> : "–"}
                </span>;
              })}
            </div>)}
          </div>
        </section>}

        {movers.length > 0 && <section className="panel">
          <h2>최근 목표주가 변경</h2>
          <p className="hint">변화율이 큰 순</p>
          <table className="stock-table">
            <tbody>{movers.map((s) => <tr key={s.id}>
              <td><Link href={stockHref(s.id)!}>{s.name}</Link><br /><span className="muted">{s.last_tp_change!.date.slice(5).replace("-", ".")} · {s.rating ?? ""}</span></td>
              <td className="num">{won(s.target_price)}<br /><b className={s.last_tp_change!.pct > 0 ? "up" : "down"}>{signedPct(s.last_tp_change!.pct)}</b></td>
            </tr>)}</tbody>
          </table>
        </section>}

        <section className="panel">
          <h2>판정 기준</h2>
          <ul className="criteria">
            <li>목표주가 한 번에 ±15% 이상</li>
            <li>같은 방향 3회 연속, 또는 30일 환산 속도가 직전의 2배 이상</li>
            <li>영업이익·EPS 추정 ±10% 이상, 흑자·적자 전환</li>
            <li>컨센서스 ±5% 이상, 추정치가 컨센서스와 ±20% 이상 차이</li>
          </ul>
          <p className="hint" style={{ margin: "8px 0 0" }}>임계값은 저장소의 config/events.json에서 바꿉니다. 투자 의견이 아니라 리포트 숫자의 변화입니다.</p>
        </section>
      </aside>
    </div>
    <ChartTooltip />
  </>;
}
