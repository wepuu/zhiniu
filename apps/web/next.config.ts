import type { NextConfig } from "next";

const apiOrigin = (process.env.API_BASE_URL ?? "http://127.0.0.1:8000")
  .replace(/\/$/, "")
  .replace(/\/api\/v1$/, "");
const distDir = process.env.ZHAONIU_NEXT_DIST_DIR ?? ".next";

const nextConfig: NextConfig = {
  distDir,
  poweredByHeader: false,
  allowedDevOrigins: ["127.0.0.1"],
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiOrigin}/api/v1/:path*`,
      },
      {
        // Some embedded browsers block localhost paths beginning with /api.
        // Keep the public REST contract unchanged and expose a same-origin UI gateway.
        source: "/gateway/api/v1/:path*",
        destination: `${apiOrigin}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
