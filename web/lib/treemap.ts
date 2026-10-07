/** Squarified treemap. items는 값 내림차순이어야 한다. */
export type Rect<T> = { x: number; y: number; w: number; h: number; item: T };

export function squarify<T>(items: { value: number; item: T }[], width: number, height: number): Rect<T>[] {
  const list = items.filter((i) => i.value > 0);
  const total = list.reduce((s, i) => s + i.value, 0);
  if (!total) return [];
  const scale = (width * height) / total;
  const rest = list.map((i) => ({ area: i.value * scale, item: i.item }));
  const out: Rect<T>[] = [];
  let x = 0, y = 0, w = width, h = height;
  const worst = (row: { area: number }[], side: number) => {
    const s = row.reduce((a, r) => a + r.area, 0);
    return Math.max(...row.map((r) => Math.max((side * side * r.area) / (s * s), (s * s) / (side * side * r.area))));
  };
  while (rest.length) {
    const side = Math.min(w, h);
    const row = [rest.shift()!];
    while (rest.length && worst([...row, rest[0]], side) <= worst(row, side)) row.push(rest.shift()!);
    const s = row.reduce((a, r) => a + r.area, 0);
    if (w >= h) {
      const cw = s / h;
      let cy = y;
      for (const r of row) { const ch = r.area / cw; out.push({ x, y: cy, w: cw, h: ch, item: r.item }); cy += ch; }
      x += cw; w -= cw;
    } else {
      const rh = s / w;
      let cx = x;
      for (const r of row) { const cw = r.area / rh; out.push({ x: cx, y, w: cw, h: rh, item: r.item }); cx += cw; }
      y += rh; h -= rh;
    }
  }
  return out;
}
