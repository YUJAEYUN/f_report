import Link from "next/link";

export default function NotFound() {
  return (
    <>
      <h1>페이지를 찾을 수 없어요</h1>
      <p><Link href="/">홈으로</Link></p>
    </>
  );
}
