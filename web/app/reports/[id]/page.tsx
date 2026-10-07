import Link from "next/link";
import { notFound } from "next/navigation";
import { allReports, decodeParam, getReport, isoWeek, toCard } from "@/lib/data";
import { Chips } from "@/components/ReportList";
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
  const card = toCard(r);
  const s = r.summary;
  const week = isoWeek(r.published_date);
  const review = r.claim_review;
  const canReview = r.report_type === "individual" && !!s;
  return (
    <>
      <p className="sub">
        <Link href={`/daily/${r.published_date}`}>{r.published_date}</Link> {r.published_time?.slice(0, 5)} ·{" "}
        {r.analyst ?? "-"} · {r.breadcrumb} · <Link href={`/weekly/${week}`}>{weekLabel(week).label}</Link>
      </p>
      <h1>{r.title}</h1>
      <div className="chips"><Chips card={card} /></div>

      {!s && <p className="warn">아직 요약되지 않은 리포트입니다.</p>}

      {s?.one_liner && (
        <section className="card">
          <p style={{ fontWeight: 600, margin: 0 }}>{s.one_liner}</p>
          {(s.ticker || s.rating || s.target_price) && (
            <dl className="kv" style={{ marginTop: 12 }}>
              {s.ticker && (<><dt>종목</dt><dd>{s.ticker}</dd></>)}
              {s.rating && (<><dt>투자의견</dt><dd>{s.rating}{s.rating_change ? ` (${s.rating_change})` : ""}</dd></>)}
              {s.target_price != null && s.target_price !== "" && (<><dt>목표주가</dt><dd>{Number(s.target_price).toLocaleString("ko-KR")}</dd></>)}
            </dl>
          )}
        </section>
      )}

      {s?.key_points && s.key_points.length > 0 && (
        <section className="card prose">
          <h2>핵심 포인트</h2>
          <ul>{s.key_points.map((p, i) => <li key={i}>{p}</li>)}</ul>
          {s.risk_factors && s.risk_factors.length > 0 && (
            <>
              <h3>리스크</h3>
              <ul>{s.risk_factors.map((p, i) => <li key={i}>{p}</li>)}</ul>
            </>
          )}
        </section>
      )}

      {r.insight && (
        <section className="card insight-card" aria-labelledby="report-insight-title">
          <div className="insight-heading">
            <div>
              <p className="eyebrow">DECISION LENS</p>
              <h2 id="report-insight-title">이 리포트에서 읽어낼 점</h2>
            </div>
            <span className="insight-perspective">판단 보조 관점</span>
          </div>
          <p className="insight-note">투자 추천이 아니라, 리포트의 논리를 변화 → 의미 → 확인 순서로 해석합니다.</p>
          <dl className="insight-grid">
            <div>
              <dt>무엇이 달라졌나</dt>
              <dd>{r.insight.change}</dd>
            </div>
            <div>
              <dt>왜 중요한가</dt>
              <dd>{r.insight.implication}</dd>
            </div>
            <div>
              <dt>무엇을 확인할까</dt>
              <dd>
                <ul>{r.insight.watch_points.map((point, i) => <li key={i}>{point}</li>)}</ul>
              </dd>
            </div>
          </dl>
        </section>
      )}

      {canReview && (
        <section className="card review-card" aria-labelledby="report-review-title">
          <div className="insight-heading">
            <div>
              <p className="eyebrow">LOGIC CHECK</p>
              <h2 id="report-review-title">AI 논리 평가</h2>
            </div>
            {review && <span className={`strength strength-${review.strength}`}>논리 강도 · {review.strength}</span>}
          </div>
          <p className="insight-note">
            결론이 맞을지가 아니라 근거에서 결론까지의 논리가 얼마나 튼튼한지를 봅니다.
            {review && (
              <>
                {" "}
                {review.input === "preview" ? "미리보기 발췌 기준 · " : ""}
                {review.generated_at.slice(0, 16).replace("T", " ")} 생성
              </>
            )}
          </p>
          {review ? (
            <div className="prose review-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(review.markdown, { escapeHtml: true }) }} />
          ) : (
            <p className="sub" style={{ margin: 0 }}>아직 평가가 없습니다.</p>
          )}
          <EvaluateButton id={r.report_id} generatedAt={review?.generated_at} />
        </section>
      )}

      {s?.items && s.items.length > 0 && (
        <section className="card prose">
          <h2>항목별 요약</h2>
          <ul>{s.items.map((it, i) => <li key={i}><strong>{it.topic}</strong> — {it.note}</li>)}</ul>
        </section>
      )}

      <section className="card">
        <h2 style={{ marginTop: 0 }}>원문</h2>
        <p className="chips">
          <a className="chip" href={r.source_url} target="_blank" rel="noreferrer">하나증권 페이지</a>
          {r.pdf_url && <a className="chip" href={r.pdf_url} target="_blank" rel="noreferrer">PDF</a>}
        </p>
        {r.pdf_error && <p className="warn">PDF 추출 실패: {r.pdf_error}</p>}
        {r.pdf_text && (
          <details className="raw">
            <summary>추출된 원문 텍스트 보기 ({r.pdf_text.length.toLocaleString("ko-KR")}자)</summary>
            <div className="raw-text">{r.pdf_text}</div>
          </details>
        )}
      </section>
    </>
  );
}
