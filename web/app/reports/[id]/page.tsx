import Link from "next/link";
import { notFound } from "next/navigation";
import { allCards, allReports, brokerOf, decodeParam, getReport, isoWeek } from "@/lib/data";
import EvaluateButton from "@/components/EvaluateButton";
import { renderMarkdown } from "@/lib/md";
import { weekLabel } from "@/lib/dashboard";
import { allEvents, getStock, METRIC_LABEL, money, reportSignals, signedPct, stockHref, won } from "@/lib/signals";
import { EventList } from "@/components/EventList";

export const dynamicParams = false;

export function generateStaticParams() {
  return allReports().map((r) => ({ id: r.report_id }));
}

export default async function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const r = getReport(decodeParam((await params).id));
  if (!r) notFound();
  const s = r.summary;
  const week = isoWeek(r.published_date);
  const review = r.claim_review;
  const canReview = r.report_type === "individual" && !!s;
  const tp = s?.target_price != null && s.target_price !== "" ? Number(s.target_price).toLocaleString("ko-KR") : null;
  // 같은 테마를 다룬 다른 최근 리포트
  const mainTheme = r.themes?.[0];
  const related = mainTheme ? allCards().filter((c) => c.id !== r.report_id && c.themes.includes(mainTheme)).slice(0, 5) : [];
  // 코드가 원문에서 읽은 숫자 (scripts/signals.py). 주인공 종목은 사이드 박스에, 나머지는 본문 표에
  const sigs = reportSignals(r.report_id);
  const main = sigs.find((x) => x.primary) ?? (sigs.length === 1 ? sigs[0] : undefined);
  const others = sigs.filter((x) => x !== main && (x.rating_change || x.estimate_revisions.length));
  const reportEvents = allEvents().filter((e) => e.report_id === r.report_id);
  const mc = main?.rating_change;
  // 이 리포트 발행일 기준 여러 증권사 목표주가 평균
  const cons = main ? getStock(main.stock_id)?.tp_consensus.filter((c) => c.date <= r.published_date).at(-1) : undefined;

  return <>
    <p className="crumb"><Link href="/reports">리포트</Link> · {brokerOf(r) && <>{brokerOf(r)} · </>}{r.desk ?? r.category} · {r.category}</p>
    <h1 className="report-title">{r.title}</h1>
    {s?.one_liner && <p className="report-lead">{s.one_liner}</p>}
    {!s && <p className="warn">아직 요약되지 않은 리포트입니다.</p>}

    <div className="report-layout">
      <article className="report-main">
        {s?.key_points && s.key_points.length > 0 && <section className="panel">
          <h2>핵심 포인트</h2>
          <ol className="points">{s.key_points.map((p, i) => <li key={i}>{p}</li>)}</ol>
          {s.risk_factors && s.risk_factors.length > 0 && <>
            <h3 className="mini-title">리스크</h3>
            <ul className="risks">{s.risk_factors.map((p, i) => <li key={i}>{p}</li>)}</ul>
          </>}
        </section>}

        {r.insight && <section className="panel" aria-labelledby="insight-title">
          <h2 id="insight-title">이 리포트에서 읽어낼 점</h2>
          <p className="hint">투자 추천이 아니라 리포트의 논리를 변화 → 의미 → 확인 순서로 풀어 봅니다.</p>
          <ol className="steps">
            <li><b>무엇이 달라졌나</b><p>{r.insight.change}</p></li>
            <li><b>왜 중요한가</b><p>{r.insight.implication}</p></li>
            {r.insight.watch_points.length > 0 && <li><b>무엇을 확인할까</b><ul>{r.insight.watch_points.map((p, i) => <li key={i}>{p}</li>)}</ul></li>}
          </ol>
        </section>}

        {(reportEvents.length > 0 || others.length > 0) && <section className="panel">
          <h2>이 리포트의 숫자 변화</h2>
          <p className="hint">원문의 투자의견·목표주가·추정치를 직전 기록과 비교한 결과입니다.</p>
          {reportEvents.length > 0 && <EventList events={reportEvents} />}
          {others.length > 0 && <div className="table-scroll"><table className="stock-table">
            <thead><tr><th>종목</th><th>투자의견</th><th className="num">목표주가</th><th className="num">변화</th></tr></thead>
            <tbody>{others.map((x) => <tr key={x.stock_id}>
              <td><Link href={stockHref(x.stock_id)!}>{x.name}</Link></td>
              <td>{x.rating_change && x.rating_change.rating_from !== x.rating_change.rating_to ? `${x.rating_change.rating_from} → ${x.rating_change.rating_to}` : x.rating ?? "-"}</td>
              <td className="num">{x.rating_change?.tp_from && x.rating_change.tp_from !== x.rating_change.tp_to ? `${x.rating_change.tp_from.toLocaleString("ko-KR")} → ` : ""}{won(x.target_price)}</td>
              <td className={`num ${(x.rating_change?.tp_pct ?? 0) > 0 ? "up" : (x.rating_change?.tp_pct ?? 0) < 0 ? "down" : ""}`}>
                {x.rating_change?.tp_pct != null ? signedPct(x.rating_change.tp_pct) : x.estimate_revisions.length ? "추정치 조정" : "-"}</td>
            </tr>)}</tbody>
          </table></div>}
        </section>}

        {canReview && <section className="panel review" aria-labelledby="review-title">
          <div className="review-head">
            <h2 id="review-title">AI 논리 평가</h2>
            {review && <span className={`strength strength-${review.strength}`}>논리 강도 · {review.strength}</span>}
          </div>
          <p className="hint">
            결론이 맞을지가 아니라 근거에서 결론까지의 논리가 얼마나 튼튼한지 봅니다.
            {review && <> {review.input === "preview" ? "미리보기 발췌 기준 · " : ""}{review.generated_at.slice(0, 16).replace("T", " ")} 생성</>}
          </p>
          {review
            ? <div className="prose review-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(review.markdown, { escapeHtml: true }) }} />
            : <p className="sub" style={{ margin: 0 }}>아직 평가가 없습니다.</p>}
          <EvaluateButton id={r.report_id} generatedAt={review?.generated_at} />
        </section>}

        {s?.items && s.items.length > 0 && <section className="panel prose">
          <h2>항목별 요약</h2>
          <ul>{s.items.map((it, i) => <li key={i}><strong>{it.topic}</strong> — {it.note}</li>)}</ul>
        </section>}

        {r.pdf_error && <section className="panel">
          <p className="warn">PDF 추출 실패: {r.pdf_error}</p>
        </section>}
      </article>

      <aside className="report-side">
        <section className="panel factbox">
          <dl>
            {main ? <>
              <dt>종목</dt><dd><Link href={stockHref(main.stock_id)!}>{main.name}</Link> <span className="muted">{main.code}</span></dd>
              <dt>투자의견</dt><dd className="strong">{mc && mc.rating_from !== mc.rating_to ? `${mc.rating_from} → ${mc.rating_to}` : main.rating ?? "-"}</dd>
              {main.target_price != null && <><dt>목표주가</dt><dd className="strong">{won(main.target_price)}
                {mc?.tp_pct != null && <span className={`tp-delta ${mc.tp_pct > 0 ? "up" : "down"}`}>{signedPct(mc.tp_pct)} <span className="muted">(이전 {mc.tp_from!.toLocaleString("ko-KR")})</span></span>}</dd></>}
              {cons && cons.n >= 2 && <><dt>컨센서스</dt><dd>{won(cons.mean)} <span className="muted">({cons.n}개사 평균)</span></dd></>}
              {main.upside_pct != null && <><dt>상승여력</dt><dd>{signedPct(main.upside_pct)} <span className="muted">(주가 {won(main.price)})</span></dd></>}
              {main.gap && <><dt>컨센 대비</dt><dd>{main.gap.year}년 {METRIC_LABEL[main.gap.metric]} {signedPct(main.gap.gap_pct, 0)} <span className="muted">({money(main.gap.estimate, main.gap.metric)} vs {money(main.gap.consensus, main.gap.metric)})</span></dd></>}
            </> : <>
              {s?.ticker && <><dt>종목</dt><dd>{s.ticker}</dd></>}
              {s?.rating && <><dt>투자의견</dt><dd className="strong">{s.rating}</dd></>}
              {tp && <><dt>목표주가</dt><dd className="strong">{tp}</dd></>}
            </>}
            {brokerOf(r) && <><dt>증권사</dt><dd>{brokerOf(r)}</dd></>}
            <dt>애널리스트</dt><dd>{r.analyst ?? "-"}</dd>
            <dt>발행</dt><dd><Link href={`/daily/${r.published_date}`}>{r.published_date}</Link> {r.published_time?.slice(0, 5)}</dd>
            <dt>주차</dt><dd><Link href={`/weekly/${week}`}>{weekLabel(week).label}</Link></dd>
          </dl>
          {(r.industries?.length ?? 0) > 0 && <div className="fact-tags"><span>산업</span>
            {r.industries!.map((i) => <Link key={i} className="chip" href={`/industries/${encodeURIComponent(i)}`}>{i}</Link>)}</div>}
          {(r.themes?.length ?? 0) > 0 && <div className="fact-tags"><span>테마</span>
            {r.themes!.map((t) => <Link key={t} className="chip theme" href={`/themes/${encodeURIComponent(t)}`}>{t}</Link>)}</div>}
          <div className="fact-links">
            <a href={r.source_url} target="_blank" rel="noreferrer">원문 페이지 ↗</a>
            {r.pdf_url && <a href={r.pdf_url} target="_blank" rel="noreferrer">PDF ↗</a>}
          </div>
        </section>

        {related.length > 0 && <section className="panel related">
          <h2>같은 테마의 다른 리포트</h2>
          <p className="hint"><Link href={`/themes/${encodeURIComponent(mainTheme!)}`}>{mainTheme}</Link></p>
          <ul>{related.map((c) => <li key={c.id}><Link href={`/reports/${c.id}`}>{c.title}</Link><span>{c.date.slice(5).replace("-", ".")} · {c.analyst ?? ""}</span></li>)}</ul>
        </section>}
      </aside>
    </div>
  </>;
}
