import type { NextConfig } from "next";

/*
 * Two build modes:
 *  - NEXT_OUTPUT=export (automatic on Cloudflare Pages) → static files in out/. The
 *    browser calls the API directly at NEXT_PUBLIC_API_BASE (CORS enforced by the API).
 *    Security headers come from public/_headers.
 *  - default (standalone) → Node server (Docker, local dev, E2E). /api/v1/* is proxied to
 *    API_URL, so NEXT_PUBLIC_API_BASE can stay empty.
 */
// Cloudflare Pages sets CF_PAGES=1 while building and can only serve static files, so a
// Pages build is always a static export, whether or not NEXT_OUTPUT was set.
const staticExport =
  process.env.NEXT_OUTPUT?.trim().toLowerCase() === "export" || process.env.CF_PAGES === "1";
const API_URL = process.env.API_URL ?? "http://localhost:8000";

/*
 * A static site has its settings baked in at build time. Stop the build with a plain message
 * when one is missing or malformed (for example pasted as a Markdown link), rather than
 * publishing a site that cannot reach the API or sign anyone in.
 */
function checkStaticSettings(): void {
  const problems: string[] = [];
  const address = (name: string, required: boolean) => {
    const value = process.env[name]?.trim() ?? "";
    if (!value) {
      if (required) problems.push(`${name} is not set.`);
      return;
    }
    if (!/^https:\/\/[^\s[\]()<>"']+$/.test(value)) {
      problems.push(`${name} must be a plain https:// address, got: ${value}`);
    }
  };
  address("NEXT_PUBLIC_API_BASE", true);
  address("NEXT_PUBLIC_SUPABASE_URL", false);
  const key =
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY?.trim() ||
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim() ||
    "";
  if (process.env.NEXT_PUBLIC_SUPABASE_URL?.trim() && !key) {
    problems.push("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY is not set (needed with NEXT_PUBLIC_SUPABASE_URL).");
  }
  if (key && /\s/.test(key)) problems.push("The Supabase key contains spaces; paste only the key.");
  if (problems.length) {
    throw new Error(
      "Static build settings need fixing (Cloudflare Pages > Settings > Variables and Secrets):\n- " +
        problems.join("\n- "),
    );
  }
}
if (staticExport) checkStaticSettings();

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
