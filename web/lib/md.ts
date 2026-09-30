import { marked } from "marked";

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
  // 태그 밖 텍스트에서만, 그리고 이미 <a> 안인 경우는 건드리지 않는다
  let inAnchor = 0;
  return html
    .split(/(<[^>]+>)/)
    .map((part) => {
      if (part.startsWith("<")) {
        if (/^<a[\s>]/i.test(part)) inAnchor++;
        else if (/^<\/a>/i.test(part)) inAnchor = Math.max(0, inAnchor - 1);
        return part;
      }
      if (inAnchor) return part;
      return part.replace(/\b(hana_\d{5,})\b/g, '<a class="rid" href="/reports/$1">$1</a>');
    })
    .join("");
}

export function renderMarkdown(md: string, opts: { dropTitle?: boolean } = {}): string {
  let source = opts.dropTitle ? md.replace(/^#\s[^\n]*\n/, "") : md;
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
