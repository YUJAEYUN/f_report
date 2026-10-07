import Link from "next/link";
import type { ReportCard } from "@/lib/data";

export function Chips({ card }: { card: ReportCard }) {
  return (
    <>
      <span className="chip desk">{card.desk}</span>
      {card.industries.map((i) => (
        <Link key={i} className="chip" href={`/industries/${encodeURIComponent(i)}`}>{i}</Link>
      ))}
      {card.themes.map((t) => (
        <Link key={t} className="chip theme" href={`/themes/${encodeURIComponent(t)}`}>{t}</Link>
      ))}
    </>
  );
}

export function ReportItem({ card, showDate = true }: { card: ReportCard; showDate?: boolean }) {
  return (
    <li>
      <div className="meta">
        {showDate && <span>{card.date}</span>}
        {card.analyst && <span>{card.analyst}</span>}
        <Chips card={card} />
        {card.badge && <span className="rc-badge">{card.badge}</span>}
      </div>
      <Link className="title" href={`/reports/${card.id}`}>{card.title}</Link>
      {card.oneLiner && <p className="one">{card.oneLiner}</p>}
    </li>
  );
}

export function ReportList({ cards, showDate = true }: { cards: ReportCard[]; showDate?: boolean }) {
  return (
    <ul className="report-list">
      {cards.map((c) => <ReportItem key={c.id} card={c} showDate={showDate} />)}
    </ul>
  );
}
