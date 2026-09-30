import { NextResponse, type NextRequest } from "next/server";

// 사이트 전체를 HTTP Basic 인증으로 보호한다 (리포트 원문 텍스트가 포함되어 있으므로).
// Vercel 프로젝트 환경변수 DASHBOARD_PASSWORD(필수), DASHBOARD_USER(선택, 기본 "me")로 설정.
export function proxy(request: NextRequest) {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) {
    if (process.env.NODE_ENV !== "production") return NextResponse.next();
    return new NextResponse("DASHBOARD_PASSWORD 환경변수가 설정되지 않았습니다.", { status: 503 });
  }
  const user = process.env.DASHBOARD_USER || "me";
  const header = request.headers.get("authorization") || "";
  const [scheme, encoded] = header.split(" ");
  if (scheme === "Basic" && encoded) {
    const decoded = atob(encoded);
    const sep = decoded.indexOf(":");
    if (sep >= 0 && decoded.slice(0, sep) === user && decoded.slice(sep + 1) === password) {
      return NextResponse.next();
    }
  }
  return new NextResponse("인증이 필요합니다.", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="research-tracker", charset="UTF-8"' },
  });
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
