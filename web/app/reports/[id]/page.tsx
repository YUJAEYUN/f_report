import Link from "next/link";
import { notFound } from "next/navigation";
import { allCards, allReports, decodeParam, getReport, isoWeek } from "@/lib/data";
import EvaluateButton from "@/components/EvaluateButton";
import { renderMarkdown } from "@/lib/md";
import { weekLabel } from "@/lib/dashboard";

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

  return <>
    <p className="crumb"><Link href="/reports">리포트</Link> · {r.desk ?? r.category} · {r.category}</p>
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
            <li><b>무엇을 확인할까</b><ul>{r.insight.watch_points.map((p, i) => <li key={i}>{p}</li>)}</ul></li>
          </ol>
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
            {s?.ticker && <><dt>종목</dt><dd>{s.ticker}</dd></>}
            {s?.rating && <><dt>투자의견</dt><dd className="strong">{s.rating}{s.rating_change && s.rating_change !== "유지" ? ` (${s.rating_change})` : ""}</dd></>}
            {tp && <><dt>목표주가</dt><dd className="strong">{tp}</dd></>}
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
