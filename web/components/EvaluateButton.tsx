"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { EvaluateStatus } from "@/lib/evaluate";

const POLL_MS = 15_000;

type View = EvaluateStatus & { error?: string; disabled?: boolean };

/** GitHub Actions의 evaluate-reports를 이 리포트만 대상으로 실행하고 진행 상태를 보여준다. */
export default function EvaluateButton({ id, generatedAt }: { id: string; generatedAt?: string }) {
  const [view, setView] = useState<View>({ state: "none" });
  const [busy, setBusy] = useState(false);
  // 실행 요청 직후에는 새 실행이 목록에 나타나기 전이라, 그보다 오래된 실행 결과는 무시한다
  const requestedAt = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    const res = await fetch(`/api/evaluate?id=${encodeURIComponent(id)}`, { cache: "no-store" });
    const body = (await res.json().catch(() => ({}))) as View;
    if (!res.ok) {
      setView({ state: "none", error: body.error, disabled: res.status === 503 });
      return;
    }
    const since = requestedAt.current;
    if (since && (!body.createdAt || Date.parse(body.createdAt) < since - 60_000)) return; // 아직 새 실행이 안 보임
    setView(body);
  }, [id]);

  const running = view.state === "queued" || view.state === "in_progress";

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!running) return;
    const t = setInterval(refresh, POLL_MS);
    return () => clearInterval(t);
  }, [running, refresh]);

  async function run() {
    if (generatedAt && !confirm("이미 평가가 있습니다. 다시 생성할까요? (구독 사용량을 씁니다)")) return;
    setBusy(true);
    try {
      const res = await fetch("/api/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id }),
      });
      const body = (await res.json().catch(() => ({}))) as View;
      if (res.ok) requestedAt.current = Date.now();
      setView(res.ok || res.status === 409 ? { ...body, error: undefined } : { state: "none", error: body.error });
    } finally {
      setBusy(false);
    }
  }

  // 완료된 실행이 화면의 평가보다 나중이면, 사이트 재배포를 기다리는 중이다
  const awaitingDeploy =
    view.state === "success" && view.createdAt && (!generatedAt || Date.parse(view.createdAt) > Date.parse(generatedAt));

  let note: React.ReactNode = null;
  if (view.error) note = <span className="warn">{view.error}</span>;
  else if (view.state === "queued") note = "평가 요청됨 · 대기 중";
  else if (view.state === "in_progress") note = "평가 중 · 보통 1~3분 걸립니다";
  else if (awaitingDeploy) note = "평가 완료 · 사이트 재배포 후 반영됩니다 (몇 분 뒤 새로고침)";
  else if (view.state === "failure") note = <span className="warn">최근 평가 실행이 실패했습니다</span>;

  return (
    <div className="review-actions">
      <button type="button" className="btn-sm" onClick={run} disabled={busy || running || view.disabled}>
        {running ? "평가 진행 중…" : generatedAt ? "다시 평가" : "AI 평가 생성"}
      </button>
      {note && (
        <span className="review-status">
          {note}
          {view.url && (running || view.state === "failure") && (
            <> · <a href={view.url} target="_blank" rel="noreferrer">실행 로그</a></>
          )}
        </span>
      )}
    </div>
  );
}
