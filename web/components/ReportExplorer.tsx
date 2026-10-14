"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { ReportCard } from "@/lib/data";
import { isoWeek, weekLabel } from "@/lib/dashboard";
import { ReportItem } from "./ReportList";

const PAGE = 50;

export default function ReportExplorer({ cards, initial = {} }: { cards: ReportCard[]; initial?: { week?: string; theme?: string; industry?: string } }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [desk, setDesk] = useState("");
  const [broker, setBroker] = useState("");
  const [industry, setIndustry] = useState(initial.industry ?? "");
  const [theme, setTheme] = useState(initial.theme ?? "");
  const [week, setWeek] = useState(initial.week ?? "");
  const [shown, setShown] = useState(PAGE);

  const options = useMemo(() => {
    const uniq = (xs: string[]) => [...new Set(xs)].sort((a, b) => a.localeCompare(b, "ko"));
    return {
      desks: uniq(cards.map((c) => c.desk)),
      brokers: uniq(cards.map((c) => c.broker).filter(Boolean)),
      industries: uniq(cards.flatMap((c) => c.industries)),
      themes: uniq(cards.flatMap((c) => c.themes)),
    };
  }, [cards]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return cards.filter(
      (c) =>
        (!desk || c.desk === desk) &&
        (!broker || c.broker === broker) &&
        (!industry || c.industries.includes(industry)) &&
        (!theme || c.themes.includes(theme)) &&
        (!week || isoWeek(c.date) === week) &&
        (!needle || `${c.title} ${c.oneLiner} ${c.analyst ?? ""}`.toLowerCase().includes(needle)),
    );
  }, [cards, q, desk, broker, industry, theme, week]);

  const reset = (fn: (v: string) => void) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    fn(e.target.value);
    setShown(PAGE);
  };
  const filter = (key: "industry" | "theme", fn: (v: string) => void) => (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    fn(value); setShown(PAGE);
    const params = new URLSearchParams(window.location.search);
    if (value) params.set(key, value); else params.delete(key);
    router.replace(`/reports${params.size ? `?${params}` : ""}`, { scroll: false });
  };
  const clearWeek = () => {
    setWeek(""); setShown(PAGE);
    const params = new URLSearchParams(window.location.search); params.delete("week");
    router.replace(`/reports${params.size ? `?${params}` : ""}`, { scroll: false });
  };
  const clear = () => { setQ(""); setDesk(""); setBroker(""); setIndustry(""); setTheme(""); setWeek(""); setShown(PAGE); router.replace("/reports"); };

  return (
    <>
      <div className="filters panel">
        <input placeholder="제목·요약·애널리스트 검색" value={q} onChange={reset(setQ)} />
        {options.brokers.length > 1 && <select value={broker} onChange={reset(setBroker)} aria-label="증권사">
          <option value="">전체 증권사</option>
          {options.brokers.map((d) => <option key={d}>{d}</option>)}
        </select>}
        <select value={desk} onChange={reset(setDesk)} aria-label="데스크">
          <option value="">전체 데스크</option>
          {options.desks.map((d) => <option key={d}>{d}</option>)}
        </select>
        <select value={industry} onChange={filter("industry", setIndustry)} aria-label="산업">
          <option value="">전체 산업</option>
          {options.industries.map((d) => <option key={d}>{d}</option>)}
        </select>
        <select value={theme} onChange={filter("theme", setTheme)} aria-label="테마">
          <option value="">전체 테마</option>
          {options.themes.map((d) => <option key={d}>{d}</option>)}
        </select>
        {week && <span className="active-filter">{weekLabel(week).label}<button onClick={clearWeek} aria-label="주차 필터 해제">×</button></span>}
      </div>
      <div className="result-head"><p className="count">{filtered.length}건</p>{(q || desk || broker || industry || theme || week) && <button className="text-button" onClick={clear}>필터 초기화</button>}</div>
      <section className="panel">
        <ul className="report-list">
          {filtered.slice(0, shown).map((c) => <ReportItem key={c.id} card={c} />)}
        </ul>
      </section>
      {filtered.length === 0 && <div className="empty"><strong>조건에 맞는 리포트가 없습니다.</strong><button className="text-button" onClick={clear}>전체 리포트 보기</button></div>}
      {shown < filtered.length && (
        <p><button className="chip" onClick={() => setShown(shown + PAGE)}>더 보기</button></p>
      )}
    </>
  );
}
