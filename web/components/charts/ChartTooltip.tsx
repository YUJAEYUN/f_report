"use client";

import { useEffect, useRef } from "react";

/** data-tip 속성이 있는 차트 요소에 올리면 수치를 띄운다. 페이지에 하나만 둔다. */
export default function ChartTooltip() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const tt = ref.current!;
    const move = (ev: PointerEvent) => {
      const t = (ev.target as Element | null)?.closest?.("[data-tip]") as HTMLElement | SVGElement | null;
      if (!t) { tt.style.opacity = "0"; return; }
      tt.textContent = t.getAttribute("data-tip");
      tt.style.opacity = "1";
      tt.style.left = `${Math.min(ev.clientX + 14, window.innerWidth - tt.offsetWidth - 8)}px`;
      tt.style.top = `${ev.clientY + 16}px`;
    };
    const hide = () => { tt.style.opacity = "0"; };
    document.addEventListener("pointermove", move);
    window.addEventListener("scroll", hide, { passive: true });
    return () => { document.removeEventListener("pointermove", move); window.removeEventListener("scroll", hide); };
  }, []);
  return <div ref={ref} className="chart-tooltip" role="tooltip" />;
}
