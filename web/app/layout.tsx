import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "리서치 트래커",
  description: "하나증권 리서치 요약·주간 인사이트",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <header className="site-header">
          <div className="wrap header-inner">
            <Link href="/" className="brand">리서치 트래커</Link>
            <nav>
              <Link href="/weekly">주간</Link>
              <Link href="/daily">일간</Link>
              <Link href="/reports">리포트</Link>
              <Link href="/themes">테마</Link>
              <Link href="/industries">산업</Link>
            </nav>
          </div>
        </header>
        <main className="wrap">{children}</main>
        <footer className="wrap site-footer">
          하나증권 리서치를 자동 요약한 개인 학습용 페이지입니다. 투자 판단의 근거로 쓰지 마세요.
        </footer>
      </body>
    </html>
  );
}
