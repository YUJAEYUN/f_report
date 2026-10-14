import Link from "next/link";
import { eventDir, eventKind, stockHref, type SignalEvent } from "@/lib/signals";

/** 숫자 변화 이벤트 목록. 판정·숫자는 코드, 이유(reason)는 리포트 본문에서 뽑은 문장 */
export function EventList({ events, showDate = false, compact = false }: { events: SignalEvent[]; showDate?: boolean; compact?: boolean }) {
  if (events.length === 0) return <p className="sub" style={{ margin: 0 }}>이 기간에 임계값을 넘은 변화가 없습니다.</p>;
  return <ul className={compact ? "events compact" : "events"}>
    {events.map((e) => {
      const dir = eventDir(e);
      const href = stockHref(e.stock_id) ?? (e.industry ? `/industries/${encodeURIComponent(e.industry)}` : null);
      return <li key={e.id} className={`event ev-${dir}`}>
        <div className="ev-head">
          <span className={`ev-kind ${dir}`}>{eventKind(e.type).label}</span>
          {href ? <Link href={href} className="ev-name">{e.name}</Link> : <b className="ev-name">{e.name}</b>}
          {showDate && <span className="ev-date">{e.date.slice(5).replace("-", ".")}</span>}
        </div>
        <p className="ev-headline">{e.headline}</p>
        {!compact && e.reason && <p className="ev-reason">{e.reason}</p>}
        {!compact && e.report_id && <Link className="ev-src" href={`/reports/${e.report_id}`}>{e.title ?? e.report_id}</Link>}
      </li>;
    })}
  </ul>;
}
