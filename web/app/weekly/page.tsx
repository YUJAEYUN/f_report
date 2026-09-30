import Link from "next/link";
import { weeklyMeta, weeks } from "@/lib/data";

export default function WeeklyIndex() {
  return (
    <>
      <h1>주간 인사이트</h1>
      <p className="sub">한 주 동안 올라온 리포트를 테마·산업 단위로 묶은 정리</p>
      <ul className="list-plain">
        {weeks().map((w) => {
          const m = weeklyMeta(w);
          return (
            <li key={w}>
              <Link href={`/weekly/${w}`}>{w}</Link>
              <span className="count">
                {m ? `리포트 ${m.report_count} · ${m.themes.map((t) => t.name).slice(0, 3).join(", ")}` : ""}
              </span>
            </li>
          );
        })}
      </ul>
    </>
  );
}
