import { allCards } from "@/lib/data";
import ReportExplorer from "@/components/ReportExplorer";

export default async function ReportsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const p = await searchParams;
  return (
    <>
      <h1>리포트</h1>
      <p className="sub">수집된 전체 리포트. 데스크·산업·테마로 거르고 제목·요약으로 검색</p>
      <ReportExplorer cards={allCards()} initial={{ week: typeof p.week === "string" ? p.week : "", theme: typeof p.theme === "string" ? p.theme : "", industry: typeof p.industry === "string" ? p.industry : "" }} />
    </>
  );
}
