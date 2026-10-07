import type { DashboardSnapshot } from "@/lib/dashboard";

/** 파이프라인 상태. 독자에게 중요한 정보는 아니라 페이지 맨 아래 한 줄로 둔다. */
export function DataStatus({ snapshot }: { snapshot: DashboardSnapshot }) {
  const q = snapshot.quality;
  return <p className="data-status" aria-label="데이터 상태">
    데이터 상태 · 최신 발행일 {snapshot.latestPublishedDate ?? "-"} · 개별 리포트 누적 {q.individualReports}건
    {" · "}<span className={q.unsummarized ? "warn" : ""}>미요약 {q.unsummarized}건</span>
    {" · "}<span className={q.pdfErrors ? "warn" : ""}>PDF 오류 {q.pdfErrors}건</span>
  </p>;
}
