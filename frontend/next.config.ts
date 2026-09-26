import type { NextConfig } from "next";

/*
 * Two build modes:
 *  - NEXT_OUTPUT=export  → static files in out/ (Cloudflare Pages / any static host). The
 *    browser calls the API directly at NEXT_PUBLIC_API_BASE (CORS enforced by the API).
 *    Security headers come from public/_headers.
 *  - default (standalone) → Node server (Docker, local dev, E2E). /api/v1/* is proxied to
 *    API_URL, so NEXT_PUBLIC_API_BASE can stay empty.
 */
const staticExport = process.env.NEXT_OUTPUT === "export";
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const config: NextConfig = staticExport
  ? { reactStrictMode: true, output: "export", trailingSlash: false, images: { unoptimized: true } }
  : {
      reactStrictMode: true,
      poweredByHeader: false,
      output: "standalone",
      async rewrites() {
        return [{ source: "/api/v1/:path*", destination: `${API_URL}/api/v1/:path*` }];
      },
      async headers() {
        return [{ source: "/:path*", headers: securityHeaders }];
      },
    };

export default config;
