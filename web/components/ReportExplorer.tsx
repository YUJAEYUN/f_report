"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ReportCard, ReportFilter } from "@/lib/data";
import { REPORT_PAGE as PAGE } from "@/lib/paging";
import { weekLabel } from "@/lib/dashboard";
import { ReportItem } from "./ReportList";

type Options = { desks: string[]; brokers: string[]; industries: string[]; themes: string[] };

/** 필터를 바꾸면 URL을 바꾸고, 서버가 걸러 낸 한 페이지(PAGE건)를 받아 그린다 */
export default function ReportExplorer({ cards, total, page, pages, filter, options }: {
  cards: ReportCard[]; total: number; page: number; pages: number; filter: ReportFilter; options: Options;
}) {
  const router = useRouter();
  const [q, setQ] = useState(filter.q);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 뒤로 가기 등으로 URL이 바뀌면 검색창도 맞춘다
  useEffect(() => setQ(filter.q), [filter.q]);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const href = (patch: Partial<ReportFilter> & { page?: number }) => {
    const next = { ...filter, ...patch };
    const params = new URLSearchParams();
    for (const k of ["q", "broker", "desk", "industry", "theme", "week"] as const) if (next[k]) params.set(k, next[k]);
    const pg = patch.page ?? 1; // 필터가 바뀌면 첫 페이지로
    if (pg > 1) params.set("page", String(pg));
    return `/reports${params.size ? `?${params}` : ""}`;
  };
  const go = (patch: Partial<ReportFilter>) => router.replace(href(patch), { scroll: false });
  const select = (key: keyof ReportFilter) => (e: React.ChangeEvent<HTMLSelectElement>) => go({ [key]: e.target.value });
  const search = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setQ(value);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => go({ q: value }), 300); // 입력이 멈추면 한 번만 요청
  };
  const active = Object.values(filter).some(Boolean);
  const clear = () => { setQ(""); router.replace("/reports"); };

  return (
    <>
      <div className="filters panel">
        <input placeholder="제목·요약·애널리스트 검색" value={q} onChange={search} />
        {options.brokers.length > 1 && <select value={filter.broker} onChange={select("broker")} aria-label="증권사">
          <option value="">전체 증권사</option>
          {options.brokers.map((d) => <option key={d}>{d}</option>)}
        </select>}
        <select value={filter.desk} onChange={select("desk")} aria-label="데스크">
          <option value="">전체 데스크</option>
          {options.desks.map((d) => <option key={d}>{d}</option>)}
        </select>
        <select value={filter.industry} onChange={select("industry")} aria-label="산업">
          <option value="">전체 산업</option>
          {options.industries.map((d) => <option key={d}>{d}</option>)}
        </select>
        <select value={filter.theme} onChange={select("theme")} aria-label="테마">
          <option value="">전체 테마</option>
          {options.themes.map((d) => <option key={d}>{d}</option>)}
        </select>
        {filter.week && <span className="active-filter">{weekLabel(filter.week).label}<button onClick={() => go({ week: "" })} aria-label="주차 필터 해제">×</button></span>}
      </div>
      <div className="result-head">
        <p className="count">{total}건{pages > 1 && ` · ${page}/${pages} 페이지`}</p>
        {active && <button className="text-button" onClick={clear}>필터 초기화</button>}
      </div>
      {cards.length > 0 && <section className="panel">
        <ul className="report-list">
          {cards.map((c) => <ReportItem key={c.id} card={c} />)}
        </ul>
      </section>}
      {total === 0 && <div className="empty"><strong>조건에 맞는 리포트가 없습니다.</strong><button className="text-button" onClick={clear}>전체 리포트 보기</button></div>}
      {pages > 1 && (
        <nav className="pager" aria-label="페이지">
          {page > 1 ? <Link href={href({ page: page - 1 })}>← 이전 {PAGE}건</Link> : <span />}
          {page < pages ? <Link href={href({ page: page + 1 })}>다음 {PAGE}건 →</Link> : <span />}
        </nav>
      )}
    </>
  );
}
