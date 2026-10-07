import type { Metadata } from "next";
import { safeNext } from "@/lib/auth";

export const metadata: Metadata = { title: "로그인 · 리서치 맵" };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const sp = await searchParams;
  const next = safeNext(typeof sp.next === "string" ? sp.next : "");
  const error = sp.error === "1";
  return (
    <div className="login">
      <form className="card login-card" method="post" action="/api/login">
        <h1>리서치 맵</h1>
        <p className="sub">개인용 페이지입니다. 로그인해 주세요.</p>
        <input type="hidden" name="next" value={next} />
        <label>
          아이디
          <input name="user" autoComplete="username" required autoFocus />
        </label>
        <label>
          비밀번호
          <input name="password" type="password" autoComplete="current-password" required />
        </label>
        {error && <p className="warn" role="alert">아이디 또는 비밀번호가 올바르지 않습니다.</p>}
        <button type="submit" className="btn">로그인</button>
      </form>
    </div>
  );
}
