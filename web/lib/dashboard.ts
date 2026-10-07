import type { Report } from "./data";

export type TrendStatus = "new" | "up" | "steady" | "down" | "dropped";
export type ThemeStat = { name: string; count: number; reportIds: string[]; analystCount: number; deskCount: number; industries: Record<string, number>; industryReportIds: Record<string, string[]> };
export type IndustryStat = { name: string; count: number; reportIds: string[]; analystCount: number };
export type DashboardWeek = { week: string; startDate: string; endDate: string; throughDate: string; reportCount: number; themes: ThemeStat[]; industries: IndustryStat[] };
export type DashboardSnapshot = {
  generatedAt: string;
  latestPublishedDate: string | null;
  quality: { totalReports: number; individualReports: number; unsummarized: number; pdfErrors: number; unclassifiedIndustries: number; unclassifiedThemes: number };
  weeks: DashboardWeek[];
};
export type ThemeChange = ThemeStat & { current: number; previous: number; delta: number; status: TrendStatus };
export type ThemeIndustryCell = { theme: string; industry: string; count: number; reportIds: string[] };

export function isoWeek(date: string): string {
  const d = new Date(`${date}T00:00:00Z`);
  const day = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  return `${d.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

export function weekBounds(week: string): [string, string] {
  const [year, n] = week.split("-W").map(Number);
  const jan4 = new Date(Date.UTC(year, 0, 4));
  const monday = new Date(jan4);
  monday.setUTCDate(jan4.getUTCDate() - ((jan4.getUTCDay() || 7) - 1) + (n - 1) * 7);
  const sunday = new Date(monday);
  sunday.setUTCDate(monday.getUTCDate() + 6);
  return [monday.toISOString().slice(0, 10), sunday.toISOString().slice(0, 10)];
}

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

/**
 * "2026-W41" -> 사람이 읽는 주차 표기.
 * 월 귀속은 그 주 목요일이 속한 달 기준 (ISO와 같은 규칙): 10/5(월)~10/11(일)이면 "10월 1주차".
 */
export function weekLabel(week: string): { month: string; label: string; range: string; full: string } {
  if (!/^\d{4}-W\d{2}$/.test(week)) return { month: week, label: week, range: "", full: week };
  const [start, end] = weekBounds(week);
  const thu = new Date(`${start}T00:00:00Z`);
  thu.setUTCDate(thu.getUTCDate() + 3);
  const nth = Math.ceil(thu.getUTCDate() / 7);
  const md = (iso: string) => {
    const d = new Date(`${iso}T00:00:00Z`);
    return `${d.getUTCMonth() + 1}.${d.getUTCDate()}(${WEEKDAYS[d.getUTCDay()]})`;
  };
  const label = `${thu.getUTCMonth() + 1}월 ${nth}주차`;
  const range = `${md(start)} – ${md(end)}`;
  return {
    month: `${thu.getUTCFullYear()}년 ${thu.getUTCMonth() + 1}월`,
    label,
    range,
    full: `${label} (${range})`,
  };
}

export function buildDashboardSnapshot(reports: Report[], generatedAt = new Date().toISOString()): DashboardSnapshot {
  const individuals = reports.filter((r) => r.report_type === "individual");
  const grouped = new Map<string, Report[]>();
  for (const report of individuals) {
    const week = isoWeek(report.published_date);
    grouped.set(week, [...(grouped.get(week) ?? []), report]);
  }
  const weeks = [...grouped.entries()].map(([week, rows]): DashboardWeek => {
    const themeMap = new Map<string, { ids: Set<string>; analysts: Set<string>; desks: Set<string>; industries: Map<string, Set<string>> }>();
    const industryMap = new Map<string, { ids: Set<string>; analysts: Set<string> }>();
    for (const r of rows) {
      const industries = [...new Set(r.industries?.length ? r.industries : ["미분류"])] as string[];
      const themes = [...new Set(r.themes?.length ? r.themes : ["미분류"])] as string[];
      for (const name of industries) {
        const v = industryMap.get(name) ?? { ids: new Set(), analysts: new Set() };
        v.ids.add(r.report_id); if (r.analyst) v.analysts.add(r.analyst); industryMap.set(name, v);
      }
      for (const name of themes) {
        const v = themeMap.get(name) ?? { ids: new Set(), analysts: new Set(), desks: new Set(), industries: new Map() };
        v.ids.add(r.report_id); if (r.analyst) v.analysts.add(r.analyst); if (r.desk) v.desks.add(r.desk);
        for (const industry of industries) {
          const ids = v.industries.get(industry) ?? new Set<string>(); ids.add(r.report_id); v.industries.set(industry, ids);
        }
        themeMap.set(name, v);
      }
    }
    const themes = [...themeMap].map(([name, v]) => ({ name, count: v.ids.size, reportIds: [...v.ids], analystCount: v.analysts.size, deskCount: v.desks.size, industries: Object.fromEntries([...v.industries].map(([k, ids]) => [k, ids.size])), industryReportIds: Object.fromEntries([...v.industries].map(([k, ids]) => [k, [...ids]])) })).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "ko"));
    const industries = [...industryMap].map(([name, v]) => ({ name, count: v.ids.size, reportIds: [...v.ids], analystCount: v.analysts.size })).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "ko"));
    const [startDate, endDate] = weekBounds(week);
    return { week, startDate, endDate, throughDate: rows.map((r) => r.published_date).sort().at(-1)!, reportCount: rows.length, themes, industries };
  }).sort((a, b) => b.week.localeCompare(a.week));
  return {
    generatedAt,
    latestPublishedDate: individuals.map((r) => r.published_date).sort().at(-1) ?? null,
    quality: {
      totalReports: reports.length, individualReports: individuals.length,
      unsummarized: reports.filter((r) => !r.summary).length, pdfErrors: reports.filter((r) => r.pdf_error).length,
      unclassifiedIndustries: individuals.filter((r) => !r.industries?.length).length,
      unclassifiedThemes: individuals.filter((r) => !r.themes?.length).length,
    }, weeks,
  };
}

export function themeChanges(snapshot: DashboardSnapshot, week: string): ThemeChange[] {
  const current = snapshot.weeks.find((w) => w.week === week);
  if (!current) return [];
  const prevDate = new Date(`${current.startDate}T00:00:00Z`); prevDate.setUTCDate(prevDate.getUTCDate() - 1);
  const previous = snapshot.weeks.find((w) => w.week === isoWeek(prevDate.toISOString().slice(0, 10)));
  const now = new Map(current.themes.map((t) => [t.name, t]));
  const before = new Map((previous?.themes ?? []).map((t) => [t.name, t]));
  const rank: Record<TrendStatus, number> = { new: 0, up: 1, steady: 2, down: 3, dropped: 4 };
  return [...new Set([...now.keys(), ...before.keys()])].map((name) => {
    const cur = now.get(name); const currentCount = cur?.count ?? 0; const previousCount = before.get(name)?.count ?? 0;
    const status: TrendStatus = previousCount === 0 ? "new" : currentCount === 0 ? "dropped" : currentCount > previousCount ? "up" : currentCount < previousCount ? "down" : "steady";
    return { ...(cur ?? { name, count: 0, reportIds: [], analystCount: 0, deskCount: 0, industries: {}, industryReportIds: {} }), current: currentCount, previous: previousCount, delta: currentCount - previousCount, status };
  }).sort((a, b) => rank[a.status] - rank[b.status] || Math.abs(b.delta) - Math.abs(a.delta) || b.current - a.current || a.name.localeCompare(b.name, "ko"));
}

export function themeIndustryMatrix(snapshot: DashboardSnapshot, week: string): ThemeIndustryCell[] {
  const selected = snapshot.weeks.find((w) => w.week === week);
  if (!selected) return [];
  return selected.themes.flatMap((t) => Object.entries(t.industries).map(([industry, count]) => ({ theme: t.name, industry, count, reportIds: t.industryReportIds[industry] ?? [] })));
}

export type PeriodRow = { name: string; current: number; previous: number; delta: number };
export type PeriodComparison = {
  week: string;
  throughDate: string;
  /** 직전 주의 같은 요일까지 (진행 중인 주를 지난주 전체와 비교하면 모든 게 줄어 보이므로) */
  previousThrough: string;
  reports: { current: number; previous: number };
  themes: PeriodRow[];
  industries: PeriodRow[];
};

function shiftDate(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** 이번 주(throughDate까지)와 직전 주 같은 기간의 개별 리포트 테마·산업 언급량 비교 */
export function comparePeriods(reports: Report[], week: string, throughDate: string): PeriodComparison {
  const [start] = weekBounds(week);
  const prevStart = shiftDate(start, -7);
  const previousThrough = shiftDate(throughDate, -7);
  const individuals = reports.filter((r) => r.report_type === "individual" && r.summary);
  const cur = individuals.filter((r) => r.published_date >= start && r.published_date <= throughDate);
  const prev = individuals.filter((r) => r.published_date >= prevStart && r.published_date <= previousThrough);
  const rows = (key: "themes" | "industries"): PeriodRow[] => {
    const count = (list: Report[]) => {
      const m = new Map<string, number>();
      for (const r of list) for (const v of new Set(r[key] ?? [])) m.set(v, (m.get(v) ?? 0) + 1);
      return m;
    };
    const a = count(cur), b = count(prev);
    return [...new Set([...a.keys(), ...b.keys()])]
      .filter((name) => name !== "미분류")
      .map((name) => ({ name, current: a.get(name) ?? 0, previous: b.get(name) ?? 0, delta: (a.get(name) ?? 0) - (b.get(name) ?? 0) }))
      .sort((x, y) => y.current - x.current || y.delta - x.delta || x.name.localeCompare(y.name, "ko"));
  };
  return {
    week, throughDate, previousThrough,
    reports: { current: cur.length, previous: prev.length },
    themes: rows("themes"),
    industries: rows("industries"),
  };
}
