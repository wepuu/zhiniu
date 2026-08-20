import type { NextConfig } from "next";

const apiOrigin = (process.env.API_BASE_URL ?? "http://127.0.0.1:8000")
  .replace(/\/$/, "")
  .replace(/\/api\/v1$/, "");

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiOrigin}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
