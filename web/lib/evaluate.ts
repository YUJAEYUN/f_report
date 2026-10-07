/** /api/evaluate 응답: 이 리포트를 대상으로 한 최근 evaluate-reports 실행 상태 */
export type EvaluateStatus = {
  state: "none" | "queued" | "in_progress" | "success" | "failure";
  createdAt?: string;
  url?: string;
};
