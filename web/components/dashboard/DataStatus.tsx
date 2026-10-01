import type { DashboardSnapshot } from "@/lib/dashboard";

export function DataStatus({ snapshot }: { snapshot: DashboardSnapshot }) {
  const q = snapshot.quality;
  return <section className="statusbar" aria-label="데이터 상태">
    <div><span>최신 발행일</span><strong>{snapshot.latestPublishedDate ?? "-"}</strong></div>
    <div><span>개별 리포트</span><strong>{q.individualReports}건</strong></div>
    <div className={q.unsummarized ? "has-warning" : ""}><span>미요약</span><strong>{q.unsummarized}건</strong></div>
    <div className={q.pdfErrors ? "has-warning" : ""}><span>PDF 오류</span><strong>{q.pdfErrors}건</strong></div>
  </section>;
}
