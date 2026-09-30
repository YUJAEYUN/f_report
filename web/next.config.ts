import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 데이터(data/, insights/, digest/)는 저장소 루트에 있고 빌드 시 읽는다
  outputFileTracingRoot: path.join(__dirname, ".."),
};

export default nextConfig;
