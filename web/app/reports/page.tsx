import Link from "next/link";
import { filterCards, reportFacets, type ReportFilter } from "@/lib/data";
import { REPORT_PAGE as PAGE } from "@/lib/paging";
import ReportExplorer from "@/components/ReportExplorer";

type Params = Record<string, string | string[] | undefined>;
const str = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

// 필터와 페이지 나누기는 서버에서 한다. 브라우저에는 지금 페이지의 카드만 보낸다.
export default async function ReportsPage({ searchParams }: { searchParams: Promise<Params> }) {
  const p = await searchParams;
  const filter: ReportFilter = {
    q: str(p.q), desk: str(p.desk), broker: str(p.broker),
    industry: str(p.industry), theme: str(p.theme), week: str(p.week),
  };
  const matched = filterCards(filter);
  const pages = Math.max(1, Math.ceil(matched.length / PAGE));
  const page = Math.min(pages, Math.max(1, Number.parseInt(str(p.page), 10) || 1));
  const cards = matched.slice((page - 1) * PAGE, page * PAGE);
  return (
    <>
      <h1>리포트</h1>
      <p className="sub">
        수집된 전체 리포트. 증권사·데스크·산업·테마로 거르고 제목·요약으로 검색 · <Link href="/daily">발행일별 다이제스트 →</Link>
      </p>
      <ReportExplorer cards={cards} total={matched.length} page={page} pages={pages} filter={filter} options={reportFacets()} />
    </>
  );
}
