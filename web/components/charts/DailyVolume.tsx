const W = 300, H = 104, BASE = H - 20;
const DAYS = ["월", "화", "수", "목", "금"];

/** 요일별 개별 리포트 건수: 지난주(회색) vs 이번 주(파랑) */
export function DailyVolume({ current, previous }: { current: (number | null)[]; previous: number[] }) {
  const max = Math.max(...previous, ...current.map((v) => v ?? 0), 1);
  const gw = (W - 10) / 5;
  return <svg viewBox={`0 0 ${W} ${H}`} className="volume" role="img" aria-label="요일별 개별 리포트 건수, 이번 주와 지난주">
    <line x1={0} x2={W} y1={BASE} y2={BASE} className="axis-line" />
    {DAYS.map((d, i) => {
      const cx = 5 + i * gw + gw / 2;
      const bar = (v: number, j: number, cls: string, label: string) => {
        const h = (v / max) * (BASE - 14);
        return <rect key={cls} x={cx - 13 + j * 14} y={BASE - h} width={12} height={Math.max(h, 1)} rx={3} className={cls} data-tip={`${d}요일 · ${label} ${v}건`} />;
      };
      return <g key={d}>
        {bar(previous[i], 0, "vol-prev", "지난주")}
        {current[i] != null && bar(current[i]!, 1, "vol-cur", "이번 주")}
        <text x={cx} y={H - 5} textAnchor="middle" className="axis-text">{d}</text>
      </g>;
    })}
  </svg>;
}
