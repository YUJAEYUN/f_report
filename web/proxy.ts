import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE, credentials, verifySession } from "@/lib/auth";

// 리서치 자료를 다루는 개인용 대시보드 전체에 로그인을 적용한다.
// Vercel 환경변수: DASHBOARD_PASSWORD(필수), DASHBOARD_USER(선택, 기본 "me")
export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (pathname === "/login" || pathname.startsWith("/api/login")) return NextResponse.next();

  if (!credentials()) {
    if (process.env.NODE_ENV !== "production") return NextResponse.next(); // 로컬 개발 편의
    return new NextResponse("DASHBOARD_PASSWORD 환경변수가 설정되지 않았습니다.", { status: 503 });
  }
  if (await verifySession(request.cookies.get(SESSION_COOKIE)?.value)) return NextResponse.next();

  const login = new URL("/login", request.url);
  if (pathname !== "/") login.searchParams.set("next", pathname + search);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
