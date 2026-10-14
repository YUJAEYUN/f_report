import Link from "next/link";
import { notFound } from "next/navigation";
import { decodeParam } from "@/lib/data";
import { allEvents, getStock, METRIC_LABEL, money, signalIndex, signedPct, stockIds, won } from "@/lib/signals";
import ChartTooltip from "@/components/charts/ChartTooltip";
import { TargetPriceChart } from "@/components/charts/TargetPriceChart";
import { EventList } from "@/components/EventList";

export const dynamicParams = false;

export function generateStaticParams() {
  return stockIds().map((id) => ({ id }));
}

export default async function StockPage({ params }: { params: Promise<{ id: string }> }) {
  const s = getStock(decodeParam((await params).id));
  if (!s) notFound();
  const last = s.timeline.at(-1);
  const lastObs = s.observations.at(-1);
  const events = allEvents().filter((e) => e.stock_id === s.id);
  const windowStart = signalIndex().window_start ?? "";
  const today = [...s.observations.map((o) => o.date), ...s.timeline.map((p) => p.date), windowStart].sort().at(-1)!;
  const tpChanges = s.rating_changes.filter((c) => c.tp_pct != null || c.rating_from !== c.rating_to).slice().reverse();
  const withEst = s.observations.filter((o) => Object.keys(o.estimates).length || Object.keys(o.consensus).length);
  const years = [...new Set(withEst.flatMap((o) => [...Object.keys(o.estimates), ...Object.keys(o.consensus)]))].sort();
  const revisions = s.estimate_revisions.filter((r) => r.metric === "op" || r.metric === "eps");
  const cons = s.tp_consensus.at(-1);
  const recentFrom = new Date(Date.parse(`${today}T00:00:00Z`) - 90 * 86400000).toISOString().slice(0, 10); // 최근 3개월
  // 증권사별 최신 의견 (차트의 표 보기 역할도 한다)
  const latestBy = new Map<string, (typeof s.timeline)[number]>();
  for (const p of s.timeline) latestBy.set(p.broker, p);
  const brokerRows = [...latestBy.values()].sort((a, b) => b.date.localeCompare(a.date));
  const lastChangeBy = new Map<string, (typeof s.rating_changes)[number]>();
  for (const c of s.rating_changes) if (c.tp_pct != null && !c.mismatch) lastChangeBy.set(c.broker, c);

  return <>
    <p className="crumb"><Link href="/signals">숫자 변화</Link>{s.industry && <> · <Link href={`/industries/${encodeURIComponent(s.industry)}`}>{s.industry}</Link></>}</p>
    <h1 className="page-title">{s.name}</h1>
    <p className="sub">{s.code ?? "종목코드 미확인"} · 증권사 {s.brokers.length}곳 · 리포트 {new Set(s.observations.map((o) => o.report_id)).size}건 · 투자의견 이력 {s.timeline.length}건</p>

    <div className="report-layout">
      <article className="report-main">
        <section className="panel">
          <h2>목표주가 추이 <span className="count">최근 3개월</span></h2>
          <p className="hint">증권사별 목표주가 계단선과 여러 증권사 평균(굵은 선). 회색 점은 리포트에 적힌 당시 주가, 빨강·파랑 점은 목표주가 상향·하향입니다. 하나증권은 리포트 속 이력표로 과거까지 이어집니다.</p>
          <TargetPriceChart timeline={s.timeline} observations={s.observations} changes={s.rating_changes} consensus={s.tp_consensus} today={today} from={recentFrom} />
          {s.timeline[0] && s.timeline[0].date < recentFrom && <details className="more-range">
            <summary>전체 기간 보기 ({s.timeline[0].date.slice(0, 7).replace("-", ".")}부터)</summary>
            <TargetPriceChart timeline={s.timeline} observations={s.observations} changes={s.rating_changes} consensus={s.tp_consensus} today={today} />
          </details>}
        </section>

        {brokerRows.length > 0 && <section className="panel">
          <h2>증권사별 최신 의견</h2>
          <div className="table-scroll">
            <table className="stock-table">
              <thead><tr><th>증권사</th><th>투자의견</th><th className="num">목표주가</th><th className="num">최근 조정</th><th className="num">기준일</th></tr></thead>
              <tbody>{brokerRows.map((p) => {
                const c = lastChangeBy.get(p.broker);
                return <tr key={p.broker}>
                  <td>{p.report_id ? <Link href={`/reports/${p.report_id}`}>{p.broker}</Link> : p.broker}</td>
                  <td>{p.rating}</td>
                  <td className="num">{won(p.target_price)}</td>
                  <td className={`num ${(c?.tp_pct ?? 0) > 0 ? "up" : (c?.tp_pct ?? 0) < 0 ? "down" : ""}`}>{c ? `${signedPct(c.tp_pct)} (${c.date.slice(5).replace("-", ".")})` : "-"}</td>
                  <td className="num">{p.date.slice(2).replaceAll("-", ".")}</td>
                </tr>;
              })}</tbody>
            </table>
          </div>
        </section>}

        {events.length > 0 && <section className="panel">
          <h2>발생한 이벤트</h2>
          <p className="hint">{windowStart} 이후 임계값을 넘은 변화</p>
          <EventList events={events} showDate />
        </section>}

        {withEst.length > 0 && <section className="panel">
          <h2>실적 추정치와 컨센서스</h2>
          <p className="hint">리포트가 나올 때마다 증권사 추정치와 리포트에 실린 시장 컨센서스를 기록합니다. 지금은 하나증권 리포트 양식에서만 읽습니다. 단위: 매출·이익은 억원/조원, EPS는 원.</p>
          <div className="table-scroll">
            <table className="stock-table est-table">
              <thead><tr><th>발행일</th><th>출처</th>{years.map((y) => <th key={y} className="num" colSpan={2}>{y}년 영업이익 · EPS</th>)}</tr></thead>
              <tbody>{withEst.slice().reverse().flatMap((o) => (["estimates", "consensus"] as const)
                .filter((k) => Object.keys(o[k]).length)
                .map((k) => <tr key={`${o.date}-${k}`}>
                  <td className="num"><Link href={`/reports/${o.report_id}`}>{o.date.slice(2).replaceAll("-", ".")}</Link></td>
                  <td>{k === "estimates" ? `${o.broker} 추정` : "시장 컨센"}</td>
                  {years.flatMap((y) => [
                    <td key={`${y}op`} className="num">{money(o[k][y]?.op, "op")}</td>,
                    <td key={`${y}eps`} className="num">{money(o[k][y]?.eps, "eps")}</td>,
                  ])}
                </tr>))}</tbody>
            </table>
          </div>
          {revisions.length > 0 && <>
            <h3 className="mini-title">추정치 변화</h3>
            <ul className="rev-list">{revisions.slice().reverse().map((r, i) => <li key={i}>
              <span>{r.date.slice(5).replace("-", ".")}</span>
              {r.broker} {r.year}년 {METRIC_LABEL[r.metric]} {money(r.from, r.metric)} → {money(r.to, r.metric)}
              <b className={(r.pct ?? 0) > 0 || r.turn === "흑자전환" ? "up" : "down"}> {r.turn ?? signedPct(r.pct)}</b>
              {r.speed30 != null && <em> · 30일 환산 {signedPct(r.speed30)}</em>}
            </li>)}</ul>
          </>}
        </section>}

        {tpChanges.length > 0 && <section className="panel">
          <h2>투자의견·목표주가 변경 이력</h2>
          <div className="table-scroll">
            <table className="stock-table">
              <thead><tr><th>날짜</th><th>증권사</th><th>투자의견</th><th className="num">목표주가</th><th className="num">변화</th><th className="num">30일 환산</th><th>출처</th></tr></thead>
              <tbody>{tpChanges.map((c) => <tr key={`${c.date}-${c.broker}`}>
                <td className="num">{c.date.slice(2).replaceAll("-", ".")}</td>
                <td>{c.broker}</td>
                <td>{c.rating_from !== c.rating_to ? `${c.rating_from} → ${c.rating_to}` : c.rating_to}{c.note ? <span className="muted"> ({c.note})</span> : null}</td>
                <td className="num">{c.tp_from && c.tp_to && c.tp_from !== c.tp_to ? `${c.tp_from.toLocaleString("ko-KR")} → ${c.tp_to.toLocaleString("ko-KR")}` : won(c.tp_to)}</td>
                <td className={`num ${(c.tp_pct ?? 0) > 0 ? "up" : (c.tp_pct ?? 0) < 0 ? "down" : ""}`}>{c.tp_pct != null ? signedPct(c.tp_pct) : "-"}</td>
                <td className="num">{c.tp_speed30 != null ? signedPct(c.tp_speed30) : "-"}</td>
                <td>{c.report_id ? <Link href={`/reports/${c.report_id}`}>리포트</Link> : <span className="muted">이력표</span>}</td>
              </tr>)}</tbody>
            </table>
          </div>
        </section>}
      </article>

      <aside className="report-side">
        <section className="panel factbox">
          <dl>
            {cons && cons.n >= 2 ? <>
              <dt>컨센서스</dt><dd className="strong">{won(cons.mean)}</dd>
              <dt>증권사</dt><dd>{cons.n}곳 평균 · {cons.date.slice(5).replace("-", ".")} 기준</dd>
            </> : <>
              <dt>투자의견</dt><dd className="strong">{last?.rating ?? "-"}</dd>
              <dt>목표주가</dt><dd className="strong">{won(last?.target_price)}</dd>
              <dt>기준</dt><dd>{last ? `${last.broker} · ${last.date}` : "-"}</dd>
            </>}
            {lastObs?.price != null && <><dt>당시 주가</dt><dd>{won(lastObs.price)} <span className="muted">({lastObs.date.slice(5).replace("-", ".")})</span></dd></>}
            {lastObs?.upside_pct != null && <><dt>상승여력</dt><dd>{signedPct(lastObs.upside_pct)}</dd></>}
            {lastObs?.gap && <><dt>컨센 대비</dt><dd>{lastObs.gap.year}년 {METRIC_LABEL[lastObs.gap.metric]} {signedPct(lastObs.gap.gap_pct, 0)}</dd></>}
          </dl>
        </section>
        <section className="panel related">
          <h2>이 종목을 다룬 리포트</h2>
          <ul>{s.observations.slice().reverse().map((o) => <li key={`${o.report_id}-${o.broker}`}>
            <Link href={`/reports/${o.report_id}`}>{o.title}</Link>
            <span>{o.date.slice(5).replace("-", ".")} · {o.broker}{o.target_price ? ` · 목표주가 ${o.target_price.toLocaleString("ko-KR")}` : ""}</span>
          </li>)}</ul>
          {s.observations.length === 0 && <p className="sub" style={{ margin: 0 }}>산업 리포트의 이력표로만 확인된 종목입니다.</p>}
        </section>
        <p className="sub">숫자는 리포트 원문에서 코드로 읽은 값이며 투자 의견이 아닙니다.</p>
      </aside>
    </div>
    <ChartTooltip />
  </>;
}
