import { NextResponse } from "next/server";
import type { EvaluateStatus } from "@/lib/evaluate";

// 리포트 상세의 "AI 평가" 버튼 → GitHub Actions evaluate-reports 워크플로를 실행/조회한다.
// 로그인 확인은 proxy가 /api/* 전체에 대해 처리한다.
// Vercel 환경변수:
//   GITHUB_DISPATCH_TOKEN (필수): 이 저장소만, Actions: Read and write 권한의 fine-grained PAT
//   GITHUB_REPO (선택, 기본 YUJAEYUN/f_report), GITHUB_REF (선택, 기본 main)
const WORKFLOW = "evaluate-reports.yml";
const ID_RE = /^[a-z]+_\d+$/;

type Run = { display_title: string; status: string; conclusion: string | null; created_at: string; html_url: string };

function config() {
  const token = process.env.GITHUB_DISPATCH_TOKEN;
  if (!token) return null;
  return { token, repo: process.env.GITHUB_REPO || "YUJAEYUN/f_report", ref: process.env.GITHUB_REF || "main" };
}

async function gh(path: string, token: string, init: RequestInit = {}) {
  return fetch(`https://api.github.com${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      ...(init.headers ?? {}),
    },
  });
}

/** 이 리포트를 대상으로 한 가장 최근 수동 실행 (run-name에 report_id가 들어 있다) */
async function latestRun(id: string, c: NonNullable<ReturnType<typeof config>>): Promise<EvaluateStatus> {
  const res = await gh(`/repos/${c.repo}/actions/workflows/${WORKFLOW}/runs?event=workflow_dispatch&per_page=30`, c.token);
  if (!res.ok) throw new Error(`GitHub ${res.status}`);
  const { workflow_runs } = (await res.json()) as { workflow_runs: Run[] };
  const run = workflow_runs.find((r) => r.display_title.split(/[\s,]+/).includes(id));
  if (!run) return { state: "none" };
  const state =
    run.status === "completed"
      ? run.conclusion === "success" ? "success" : "failure"
      : run.status === "in_progress" ? "in_progress" : "queued";
  return { state, createdAt: run.created_at, url: run.html_url };
}

function validId(id: unknown): id is string {
  return typeof id === "string" && ID_RE.test(id);
}

export async function GET(request: Request) {
  const id = new URL(request.url).searchParams.get("id");
  if (!validId(id)) return NextResponse.json({ error: "잘못된 리포트 id" }, { status: 400 });
  const c = config();
  if (!c) return NextResponse.json({ error: "GITHUB_DISPATCH_TOKEN이 설정되지 않았습니다." }, { status: 503 });
  try {
    return NextResponse.json(await latestRun(id, c));
  } catch (e) {
    return NextResponse.json({ error: `실행 상태 조회 실패: ${(e as Error).message}` }, { status: 502 });
  }
}

export async function POST(request: Request) {
  // JSON 본문만 받는다: 다른 사이트의 form 전송으로는 이 Content-Type을 만들 수 없다
  if (!request.headers.get("content-type")?.startsWith("application/json")) {
    return NextResponse.json({ error: "application/json 요청만 받습니다." }, { status: 415 });
  }
  const { id } = (await request.json().catch(() => ({}))) as { id?: unknown };
  if (!validId(id)) return NextResponse.json({ error: "잘못된 리포트 id" }, { status: 400 });
  const c = config();
  if (!c) return NextResponse.json({ error: "GITHUB_DISPATCH_TOKEN이 설정되지 않았습니다." }, { status: 503 });
  try {
    const current = await latestRun(id, c);
    if (current.state === "queued" || current.state === "in_progress") {
      return NextResponse.json({ ...current, error: "이미 평가가 진행 중입니다." }, { status: 409 });
    }
    const res = await gh(`/repos/${c.repo}/actions/workflows/${WORKFLOW}/dispatches`, c.token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ref: c.ref, inputs: { report_ids: id, redo: "true", limit: "1" } }),
    });
    if (!res.ok) throw new Error(`GitHub ${res.status} ${(await res.text()).slice(0, 200)}`);
  } catch (e) {
    return NextResponse.json({ error: `평가 실행 요청 실패: ${(e as Error).message}` }, { status: 502 });
  }
  return NextResponse.json({ state: "queued", createdAt: new Date().toISOString() } satisfies EvaluateStatus, { status: 202 });
}
