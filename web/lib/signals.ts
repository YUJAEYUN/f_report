// scripts/signals.py가 만든 data/stocks, data/events, data/signals 를 읽는다.
import fs from "node:fs";
import path from "node:path";

const REPO = path.join(process.cwd(), "..");
const STOCKS_DIR = path.join(REPO, "data", "stocks");
const EVENTS_DIR = path.join(REPO, "data", "events");
const SIGNALS_DIR = path.join(REPO, "data", "signals");

export type Metric = "revenue" | "op" | "net" | "eps";
export type YearValues = Partial<Record<Metric, number | null>>;

export type SignalEvent = {
  id: string;
  date: string;
  type: string;
  severity: number;
  stock_id: string | null;
  code: string | null;
  name: string;
  industry: string | null;
  report_id: string | null;
  title: string | null;
  headline: string;
  reason?: string | null;
  data: Record<string, unknown>;
};

export type TimelinePoint = {
  date: string;
  rating: string;
  target_price: number | null;
  source: "table" | "report";
  report_id: string | null;
};

export type RatingChange = {
  date: string;
  prev_date: string;
  days: number;
  rating_from: string;
  rating_to: string;
  tp_from: number | null;
  tp_to: number | null;
  tp_pct: number | null;
  tp_speed30: number | null;
  report_id: string | null;
  mismatch?: boolean;
  note?: string;
};

export type Revision = {
  date: string;
  prev_date: string;
  days: number;
  year: string;
  metric: Metric;
  from: number;
  to: number;
  pct: number | null;
  speed30: number | null;
  turn: string | null;
  report_id: string;
};

export type StockObservation = {
  date: string;
  report_id: string;
  title: string;
  primary: boolean;
  rating: string | null;
  target_price: number | null;
  price: number | null;
  upside_pct: number | null;
  estimates: Record<string, YearValues>;
  consensus: Record<string, YearValues>;
  gap?: { year: string; metric: Metric; estimate: number; consensus: number; gap_pct: number };
};

export type Stock = {
  id: string;
  code: string | null;
  name: string;
  industry: string | null;
  timeline: TimelinePoint[];
  notes: { date: string; note: string }[];
  observations: StockObservation[];
  rating_changes: RatingChange[];
  estimate_revisions: Revision[];
  consensus_changes: Revision[];
  events: string[];
};

export type StockSummary = {
  id: string;
  code: string | null;
  name: string;
  industry: string | null;
  rating: string | null;
  target_price: number | null;
  rating_date: string | null;
  price: number | null;
  price_date: string | null;
  last_tp_change: { date: string; pct: number } | null;
  events: number;
  last_event_date: string | null;
  reports: number;
};

export type ReportSignal = {
  stock_id: string;
  name: string;
  code: string | null;
  primary: boolean;
  rating: string | null;
  rating_status: string | null;
  target_price: number | null;
  price: number | null;
  upside_pct: number | null;
  rating_change: { rating_from: string; rating_to: string; tp_from: number | null; tp_to: number | null; tp_pct: number | null; prev_date: string } | null;
  estimate_revisions: Revision[];
  gap: StockObservation["gap"] | null;
};

export type IndustryWeek = { up: number; down: number; flat: number; stocks: number; ratio: number };

function readJson<T>(file: string, fallback: T): T {
  return fs.existsSync(file) ? (JSON.parse(fs.readFileSync(file, "utf-8")) as T) : fallback;
}

let indexCache: { window_start: string | null; stocks: StockSummary[] } | null = null;
export function signalIndex() {
  return (indexCache ??= readJson(path.join(SIGNALS_DIR, "index.json"), { window_start: null, stocks: [] as StockSummary[] }));
}

export function stockIds(): string[] {
  return fs.existsSync(STOCKS_DIR) ? fs.readdirSync(STOCKS_DIR).filter((f) => f.endsWith(".json")).map((f) => f.slice(0, -5)) : [];
}

export function getStock(id: string): Stock | null {
  const f = path.join(STOCKS_DIR, `${id}.json`);
  return fs.existsSync(f) ? readJson<Stock | null>(f, null) : null;
}

let eventCache: SignalEvent[] | null = null;
/** 전체 이벤트. 최신 날짜 → 중요도 순 */
export function allEvents(): SignalEvent[] {
  if (eventCache) return eventCache;
  const files = fs.existsSync(EVENTS_DIR) ? fs.readdirSync(EVENTS_DIR).filter((f) => /^\d{4}-\d{2}-\d{2}\.json$/.test(f)).sort().reverse() : [];
  eventCache = files.flatMap((f) => readJson<SignalEvent[]>(path.join(EVENTS_DIR, f), []));
  return eventCache;
}

export function eventsOn(date: string): SignalEvent[] {
  return allEvents().filter((e) => e.date === date);
}

let reportMap: Record<string, ReportSignal[]> | null = null;
export function reportSignals(reportId: string): ReportSignal[] {
  reportMap ??= readJson(path.join(SIGNALS_DIR, "reports.json"), {} as Record<string, ReportSignal[]>);
  return reportMap[reportId] ?? [];
}

export function industryRevisions(): Record<string, Record<string, IndustryWeek>> {
  return readJson(path.join(SIGNALS_DIR, "industry_revisions.json"), {});
}

// ---------- 표시용 ----------

export const METRIC_LABEL: Record<Metric, string> = { revenue: "매출액", op: "영업이익", net: "순이익", eps: "EPS" };

/** 이벤트 유형 -> 짧은 라벨과 방향(색) */
export function eventKind(type: string): { label: string; dir: "up" | "down" | "flat" } {
  const map: Record<string, [string, "up" | "down" | "flat"]> = {
    tp_up: ["목표주가 상향", "up"], tp_down: ["목표주가 하향", "down"],
    tp_streak: ["연속 조정", "flat"], tp_accel: ["속도 가속", "flat"],
    rating_up: ["의견 상향", "up"], rating_down: ["의견 하향", "down"],
    coverage_start: ["커버리지 시작", "flat"], coverage_end: ["의견 해제", "flat"],
    est_up: ["추정치 상향", "up"], est_down: ["추정치 하향", "down"], est_turn: ["추정 전환", "flat"],
    cons_up: ["컨센서스 상향", "up"], cons_down: ["컨센서스 하향", "down"], cons_turn: ["컨센서스 전환", "flat"],
    gap_above: ["컨센서스보다 높음", "up"], gap_below: ["컨센서스보다 낮음", "down"],
    industry_up: ["산업 방향 전환", "up"], industry_down: ["산업 방향 전환", "down"],
  };
  const [label, dir] = map[type] ?? [type, "flat"];
  return { label, dir };
}

/** 연속·가속 이벤트의 방향은 data.tp_pct 부호로 */
export function eventDir(e: SignalEvent): "up" | "down" | "flat" {
  const k = eventKind(e.type).dir;
  if (k !== "flat") return k;
  const p = (e.data as { tp_pct?: number }).tp_pct;
  if (typeof p === "number") return p > 0 ? "up" : "down";
  if (e.type === "est_turn" || e.type === "cons_turn") return /흑자/.test(e.headline) ? "up" : "down";
  return "flat";
}

export function won(v: number | null | undefined): string {
  return v == null ? "-" : `${Math.round(v).toLocaleString("ko-KR")}원`;
}

/** 십억원 단위 값을 읽기 쉽게 (EPS는 원) */
export function money(v: number | null | undefined, metric: Metric): string {
  if (v == null) return "-";
  if (metric === "eps") return `${Math.round(v).toLocaleString("ko-KR")}원`;
  if (Math.abs(v) >= 1000) return `${(v / 1000).toLocaleString("ko-KR", { maximumFractionDigits: 2 })}조원`;
  return `${Math.round(v * 10).toLocaleString("ko-KR")}억원`;
}

export function signedPct(p: number | null | undefined, digits = 1): string {
  if (p == null) return "-";
  return `${p > 0 ? "+" : ""}${p.toFixed(digits)}%`;
}

export function stockHref(id: string | null): string | null {
  return id ? `/stocks/${encodeURIComponent(id)}` : null;
}
