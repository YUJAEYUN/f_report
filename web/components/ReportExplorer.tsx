"use client";

import { useMemo, useState } from "react";
import type { ReportCard } from "@/lib/data";
import { ReportItem } from "./ReportList";

const PAGE = 50;

export default function ReportExplorer({ cards }: { cards: ReportCard[] }) {
  const [q, setQ] = useState("");
  const [desk, setDesk] = useState("");
  const [industry, setIndustry] = useState("");
  const [theme, setTheme] = useState("");
  const [shown, setShown] = useState(PAGE);

  const options = useMemo(() => {
    const uniq = (xs: string[]) => [...new Set(xs)].sort((a, b) => a.localeCompare(b, "ko"));
    return {
      desks: uniq(cards.map((c) => c.desk)),
      industries: uniq(cards.flatMap((c) => c.industries)),
      themes: uniq(cards.flatMap((c) => c.themes)),
    };
  }, [cards]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return cards.filter(
      (c) =>
        (!desk || c.desk === desk) &&
        (!industry || c.industries.includes(industry)) &&
        (!theme || c.themes.includes(theme)) &&
        (!needle || `${c.title} ${c.oneLiner} ${c.analyst ?? ""}`.toLowerCase().includes(needle)),
    );
  }, [cards, q, desk, industry, theme]);

  const reset = (fn: (v: string) => void) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    fn(e.target.value);
    setShown(PAGE);
  };

  return (
    <>
      <div className="filters">
        <input placeholder="제목·요약·애널리스트 검색" value={q} onChange={reset(setQ)} />
        <select value={desk} onChange={reset(setDesk)} aria-label="데스크">
          <option value="">전체 데스크</option>
          {options.desks.map((d) => <option key={d}>{d}</option>)}
        </select>
        <select value={industry} onChange={reset(setIndustry)} aria-label="산업">
          <option value="">전체 산업</option>
          {options.industries.map((d) => <option key={d}>{d}</option>)}
        </select>
        <select value={theme} onChange={reset(setTheme)} aria-label="테마">
          <option value="">전체 테마</option>
          {options.themes.map((d) => <option key={d}>{d}</option>)}
        </select>
      </div>
      <p className="count">{filtered.length}건</p>
      <ul className="report-list">
        {filtered.slice(0, shown).map((c) => <ReportItem key={c.id} card={c} />)}
      </ul>
      {shown < filtered.length && (
        <p><button className="chip" onClick={() => setShown(shown + PAGE)}>더 보기</button></p>
      )}
    </>
  );
}
