import Link from "next/link";
import { weeklyMeta, weeks } from "@/lib/data";
import { weekLabel } from "@/lib/dashboard";

export default function WeeklyIndex() {
  const rows = weeks().map((w) => ({ week: w, meta: weeklyMeta(w), ...weekLabel(w) }));
  const max = Math.max(1, ...rows.map((r) => r.meta?.report_count ?? 0));
  // 최신순 목록을 달 단위로 묶는다
  const months: { month: string; rows: typeof rows }[] = [];
  for (const r of rows) {
    const last = months.at(-1);
    if (last?.month === r.month) last.rows.push(r);
    else months.push({ month: r.month, rows: [r] });
  }
  return (
    <>
      <h1>주간 인사이트</h1>
      <p className="sub">한 주(월~일) 동안 올라온 리포트를 테마·산업 단위로 묶은 정리</p>
      {months.map((m) => (
        <section key={m.month} className="week-month">
          <h2>{m.month}</h2>
          <ul className="week-list">
            {m.rows.map((r, i) => (
              <li key={r.week}>
                <Link href={`/weekly/${r.week}`} className="week-row">
                  <span className="week-when">
                    <strong>{r.label}</strong>
                    {m === months[0] && i === 0 && <span className="week-latest">최신</span>}
                    <span className="week-range">{r.range}</span>
                  </span>
                  <span className="week-bar" aria-hidden="true">
                    <span style={{ width: `${((r.meta?.report_count ?? 0) / max) * 100}%` }} />
                  </span>
                  <span className="week-count">{r.meta ? `리포트 ${r.meta.report_count}건` : ""}</span>
                  {r.meta && r.meta.themes.length > 0 && (
                    <span className="week-themes">{r.meta.themes.map((t) => t.name).slice(0, 3).join(" · ")}</span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}
