// 빌드 시 저장소 루트의 data/, insights/, digest/ 를 읽는다. 모든 페이지는 정적으로 생성된다.
import fs from "node:fs";
import path from "node:path";

const REPO = path.join(process.cwd(), "..");
const REPORTS_DIR = path.join(REPO, "data", "reports");
const INDUSTRIES_DIR = path.join(REPO, "data", "industries");
const WEEKLY_DIR = path.join(REPO, "insights", "weekly");
const DIGEST_DIR = path.join(REPO, "digest");
const TAXONOMY_PATH = path.join(REPO, "config", "taxonomy.json");

export type IndividualSummary = {
  one_liner?: string;
  ticker?: string | null;
  rating?: string | null;
  rating_change?: string | null;
  target_price?: number | string | null;
  key_points?: string[];
  risk_factors?: string[];
};
export type DailySummary = { items?: { topic: string; note: string }[] };
export type ReportInsight = {
  change: string;
  implication: string;
  watch_points: string[];
};

export type Report = {
  report_id: string;
  report_type: "individual" | "daily_series";
  title: string;
  analyst: string | null;
  published_date: string;
  published_time: string | null;
  category: string;
  breadcrumb: string;
  source_url: string;
  pdf_url: string | null;
  pdf_text: string | null;
  pdf_error?: string;
  desk?: string;
  industries?: string[];
  themes?: string[];
  summary?: IndividualSummary & DailySummary;
  insight?: ReportInsight;
  summarized_at?: string;
  tagged_at?: string;
};

/** 목록 화면용 경량 레코드 (원문 제외) */
export type ReportCard = {
  id: string;
  type: Report["report_type"];
  date: string;
  time: string | null;
  title: string;
  analyst: string | null;
  desk: string;
  industries: string[];
  themes: string[];
  oneLiner: string;
};

function readJson<T>(file: string): T {
  return JSON.parse(fs.readFileSync(file, "utf-8")) as T;
}

function listDir(dir: string): string[] {
  return fs.existsSync(dir) ? fs.readdirSync(dir) : [];
}

let reportCache: Report[] | null = null;

/** 전체 리포트, 최신순 */
export function allReports(): Report[] {
  if (reportCache) return reportCache;
  const out: Report[] = [];
  for (const day of listDir(REPORTS_DIR)) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) continue; // .gitkeep 등
    for (const f of listDir(path.join(REPORTS_DIR, day))) {
      if (f.endsWith(".json")) out.push(readJson<Report>(path.join(REPORTS_DIR, day, f)));
    }
  }
  out.sort((a, b) =>
    `${b.published_date} ${b.published_time ?? ""} ${b.report_id}`.localeCompare(
      `${a.published_date} ${a.published_time ?? ""} ${a.report_id}`,
    ),
  );
  reportCache = out;
  return out;
}

export function getReport(id: string): Report | undefined {
  return allReports().find((r) => r.report_id === id);
}

export function toCard(r: Report): ReportCard {
  const oneLiner =
    r.summary?.one_liner ??
    (r.summary?.items ?? []).slice(0, 3).map((i) => i.topic).join(" · ");
  return {
    id: r.report_id,
    type: r.report_type,
    date: r.published_date,
    time: r.published_time,
    title: r.title,
    analyst: r.analyst,
    desk: r.desk ?? (r.report_type === "daily_series" ? "데일리" : "기타"),
    industries: r.industries ?? [],
    themes: r.themes ?? [],
    oneLiner: oneLiner || "",
  };
}

export function allCards(): ReportCard[] {
  return allReports().map(toCard);
}

// ---------- 대시보드 ----------
import { buildDashboardSnapshot } from "./dashboard";
let dashboardCache: ReturnType<typeof buildDashboardSnapshot> | null = null;
export function dashboardSnapshot() {
  if (!dashboardCache) {
    const reports = allReports();
    const generatedAt = reports.map((r) => r.summarized_at ?? r.tagged_at ?? "").sort().at(-1) || new Date().toISOString();
    dashboardCache = buildDashboardSnapshot(reports, generatedAt);
  }
  return dashboardCache;
}

// ---------- 주간 인사이트 ----------

export type WeeklyMeta = {
  week: string;
  report_count: number;
  themes: { name: string; report_ids: string[] }[];
  industries: { name: string; report_ids: string[] }[];
  generated_at?: string;
};

export function weeks(): string[] {
  return listDir(WEEKLY_DIR)
    .filter((f) => f.endsWith(".md"))
    .map((f) => f.replace(/\.md$/, ""))
    .sort()
    .reverse();
}

export function weeklyMarkdown(week: string): string | null {
  const f = path.join(WEEKLY_DIR, `${week}.md`);
  return fs.existsSync(f) ? fs.readFileSync(f, "utf-8") : null;
}

export function weeklyMeta(week: string): WeeklyMeta | null {
  const f = path.join(WEEKLY_DIR, `${week}.json`);
  return fs.existsSync(f) ? readJson<WeeklyMeta>(f) : null;
}

// ---------- 일간 다이제스트 ----------

export function digestDates(): string[] {
  return listDir(DIGEST_DIR)
    .filter((f) => /^\d{4}-\d{2}-\d{2}\.md$/.test(f))
    .map((f) => f.replace(/\.md$/, ""))
    .sort()
    .reverse();
}

export function digestMarkdown(date: string): string | null {
  const f = path.join(DIGEST_DIR, `${date}.md`);
  return fs.existsSync(f) ? fs.readFileSync(f, "utf-8") : null;
}

// ---------- 산업 / 테마 ----------

export function taxonomy(): { industries: Record<string, string>; desks: Record<string, string[]> } {
  return readJson(TAXONOMY_PATH);
}

export function industryBriefs(industry: string): { week: string; markdown: string }[] {
  const dir = path.join(INDUSTRIES_DIR, industry, "briefs");
  return listDir(dir)
    .filter((f) => f.endsWith(".md"))
    .sort()
    .reverse()
    .map((f) => ({ week: f.replace(/\.md$/, ""), markdown: fs.readFileSync(path.join(dir, f), "utf-8") }));
}

export function countBy(cards: ReportCard[], key: "industries" | "themes"): [string, number][] {
  const counts = new Map<string, number>();
  for (const c of cards) for (const v of c[key]) counts.set(v, (counts.get(v) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "ko"));
}

/** ISO 주차 (파이썬 파이프라인의 iso_week와 동일) */
export function isoWeek(date: string): string {
  const d = new Date(`${date}T00:00:00Z`);
  const day = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  return `${d.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

/** 마크다운에서 '## 제목' 섹션 본문만 떼어낸다 */
export function section(markdown: string, heading: RegExp): string | null {
  const lines = markdown.split("\n");
  const start = lines.findIndex((l) => /^##\s/.test(l) && heading.test(l));
  if (start < 0) return null;
  let end = lines.findIndex((l, i) => i > start && /^##\s/.test(l));
  if (end < 0) end = lines.length;
  return lines.slice(start + 1, end).join("\n").trim();
}

/** 동적 세그먼트 값이 인코딩된 채로 들어오는 경우를 대비 */
export function decodeParam(v: string): string {
  try {
    return decodeURIComponent(v);
  } catch {
    return v;
  }
}
