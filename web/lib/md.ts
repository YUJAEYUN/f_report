import { marked } from "marked";
import { weekLabel } from "./dashboard";

// 파이프라인이 만든 마크다운은 저장소 파일 기준 상대경로로 서로를 링크한다.
// 대시보드 경로로 바꾸고, 본문의 report_id(hana_1288839)는 리포트 상세로 연결한다.
function rewriteHref(href: string): string {
  const m1 = href.match(/data\/industries\/([^/]+)\/briefs\/([^/]+)\.md$/);
  if (m1) return `/industries/${m1[1]}#${m1[2]}`;
  const m2 = href.match(/insights\/weekly\/([^/]+)\.md$/);
  if (m2) return `/weekly/${m2[1]}`;
  const m3 = href.match(/digest\/(\d{4}-\d{2}-\d{2})\.md$/);
  if (m3) return `/daily/${m3[1]}`;
  return href;
}

function linkReportIds(html: string): string {
  // 태그 밖 텍스트에서만, 그리고 이미 <a> 안인 경우는 report_id 링크를 걸지 않는다
  let inAnchor = 0;
  return html
    .split(/(<[^>]+>)/)
    .map((part) => {
      if (part.startsWith("<")) {
        if (/^<a[\s>]/i.test(part)) inAnchor++;
        else if (/^<\/a>/i.test(part)) inAnchor = Math.max(0, inAnchor - 1);
        return part;
      }
      // 본문의 ISO 주차(2026-W41)는 읽기 쉬운 "10월 2주차"로 바꾼다 (링크 주소는 태그 안이라 그대로)
      part = part.replace(/\b(\d{4}-W\d{2})\b/g, (w) => weekLabel(w).label);
      if (inAnchor) return part;
      return part.replace(/\b(hana_\d{5,})\b/g, '<a class="rid" href="/reports/$1">$1</a>');
    })
    .join("");
}

export function renderMarkdown(md: string, opts: { dropTitle?: boolean; escapeHtml?: boolean } = {}): string {
  let source = opts.dropTitle ? md.replace(/^#\s[^\n]*\n/, "") : md;
  // 외부 원문을 읽고 쓴 LLM 출력은 날 HTML이 섞여 들어오지 않게 글자로 취급한다
  if (opts.escapeHtml) source = source.replace(/&/g, "&amp;").replace(/</g, "&lt;");
  // "3.75~4.00%", "9/23~25" 같은 범위 표기가 GFM 취소선(~...~)으로 렌더링되지 않게 이스케이프
  source = source.replace(/(?<!\\)~/g, "\\~");
  const html = marked.parse(source, { async: false, gfm: true }) as string;
  const rewritten = html.replace(/href="([^"]+)"/g, (_, href: string) => {
    let decoded = href;
    try {
      decoded = decodeURI(href);
    } catch {}
    return `href="${rewriteHref(decoded)}"`;
  });
  return linkReportIds(rewritten);
}

/** "## 제목" 섹션 안의 "### 소제목" 단위로 나눈다. 소제목 앞 번호("1. ")와 뒤 건수("(9건)")는 뗀다. */
export function subsections(md: string): { title: string; body: string }[] {
  const out: { title: string; body: string }[] = [];
  for (const chunk of md.split(/^### /m).slice(1)) {
    const nl = chunk.indexOf("\n");
    const title = (nl < 0 ? chunk : chunk.slice(0, nl)).replace(/^\d+\.\s*/, "").replace(/\s*\(\d+건\)\s*$/, "").trim();
    out.push({ title, body: nl < 0 ? "" : chunk.slice(nl + 1).trim() });
  }
  return out;
}

/** 렌더링된 HTML의 report_id 링크(hana_123)를 짧은 리포트 제목으로 바꾼다. 근거 표시를 읽기 쉽게 하려는 용도 */
export function withReportTitles(html: string, titles: Map<string, string>): string {
  return html.replace(/<a class="rid" href="\/reports\/([^"]+)">[^<]*<\/a>/g, (m, id: string) => {
    const t = titles.get(id);
    if (!t) return m;
    const short = t.length > 22 ? `${t.slice(0, 21)}…` : t;
    return `<a class="ref" href="/reports/${id}" title="${t.replace(/"/g, "&quot;")}">${short.replace(/</g, "&lt;")}</a>`;
  }).replace(/\(((?:<a class="ref"[^>]*>[^<]*<\/a>(?:,\s*)?)+)\)/g, "$1"); // "(근거1, 근거2)"의 괄호는 뗀다
}
