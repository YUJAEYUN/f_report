// 로그인 세션: 서명된 쿠키. proxy와 route handler 양쪽에서 쓰므로 Web Crypto만 사용한다.
export const SESSION_COOKIE = "rt_session";
export const SESSION_DAYS = 30;

const enc = new TextEncoder();

function toHex(buf: ArrayBuffer): string {
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function credentials(): { user: string; password: string } | null {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) return null;
  return { user: process.env.DASHBOARD_USER || "me", password };
}

// 서명 키: DASHBOARD_SECRET이 있으면 그것, 없으면 아이디+비밀번호에서 파생.
// 비밀번호를 바꾸면 기존 세션은 모두 무효가 된다.
async function key(): Promise<CryptoKey> {
  const c = credentials();
  const material = process.env.DASHBOARD_SECRET || `${c?.user}:${c?.password}`;
  const digest = await crypto.subtle.digest("SHA-256", enc.encode(`rt-session:${material}`));
  return crypto.subtle.importKey("raw", digest, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
}

async function sign(payload: string): Promise<string> {
  return toHex(await crypto.subtle.sign("HMAC", await key(), enc.encode(payload)));
}

function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export async function createSession(): Promise<string> {
  const exp = String(Date.now() + SESSION_DAYS * 86400_000);
  return `${exp}.${await sign(exp)}`;
}

export async function verifySession(token: string | undefined): Promise<boolean> {
  if (!token || !credentials()) return false;
  const [exp, sig] = token.split(".");
  if (!exp || !sig || Number(exp) < Date.now()) return false;
  return safeEqual(sig, await sign(exp));
}

export async function checkLogin(user: string, password: string): Promise<boolean> {
  const c = credentials();
  if (!c) return false;
  // 길이 차이로 시간이 새지 않도록 해시끼리 비교
  const h = async (s: string) => toHex(await crypto.subtle.digest("SHA-256", enc.encode(s)));
  return safeEqual(await h(`${user}\n${password}`), await h(`${c.user}\n${c.password}`));
}

/** 로그인 후 돌아갈 경로. 외부 URL로 튕기지 않게 사이트 내부 경로만 허용 */
export function safeNext(next: string | null | undefined): string {
  return next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/login") ? next : "/";
}
