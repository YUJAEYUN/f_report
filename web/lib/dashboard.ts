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

function weekBounds(week: string): [string, string] {
  const [year, n] = week.split("-W").map(Number);
  const jan4 = new Date(Date.UTC(year, 0, 4));
  const monday = new Date(jan4);
  monday.setUTCDate(jan4.getUTCDate() - ((jan4.getUTCDay() || 7) - 1) + (n - 1) * 7);
  const sunday = new Date(monday);
  sunday.setUTCDate(monday.getUTCDate() + 6);
  return [monday.toISOString().slice(0, 10), sunday.toISOString().slice(0, 10)];
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
