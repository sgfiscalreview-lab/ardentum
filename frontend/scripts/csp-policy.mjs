// The website's Content-Security-Policy, shared by the static build (scripts/add-csp.mjs
// writes it into out/_headers) and the Node server (next.config.ts). Next.js inlines small
// scripts in its pages and static hosting has no per-request nonce, so scripts are limited
// to this site plus inline; everything else is locked to what the app uses. The API and
// Supabase addresses are build settings.
const origin = (value) => {
  try {
    return value ? new URL(value.trim()).origin : null;
  } catch {
    return null;
  }
};

export function contentSecurityPolicy(env) {
  const connect = ["'self'", origin(env.NEXT_PUBLIC_API_BASE), origin(env.NEXT_PUBLIC_SUPABASE_URL)].filter(Boolean);
  return [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    `connect-src ${[...new Set(connect)].join(" ")}`,
    "frame-ancestors 'none'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");
}
