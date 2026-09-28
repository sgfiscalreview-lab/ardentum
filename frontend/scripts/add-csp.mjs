// After a static export, writes the full Content-Security-Policy into out/_headers
// (Cloudflare Pages / Netlify). It is built here rather than kept in public/_headers
// because the addresses the page may call (the API and Supabase) are build settings.
// Next.js inlines small scripts in exported pages and there is no per-request nonce on
// static hosting, so scripts are limited to this site plus inline; everything else is
// locked to what the app actually uses.
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const file = join(dirname(fileURLToPath(import.meta.url)), "..", "out", "_headers");
if (!existsSync(file)) process.exit(0); // not a static export

const origin = (value) => {
  try {
    return value ? new URL(value.trim()).origin : null;
  } catch {
    return null;
  }
};
const connect = ["'self'", origin(process.env.NEXT_PUBLIC_API_BASE), origin(process.env.NEXT_PUBLIC_SUPABASE_URL)].filter(Boolean);

export const policy = [
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

const lines = readFileSync(file, "utf8").split("\n");
const at = lines.findIndex((l) => l.trim().startsWith("Content-Security-Policy:"));
if (at < 0) throw new Error("out/_headers has no Content-Security-Policy line to replace.");
lines[at] = `  Content-Security-Policy: ${policy}`;
writeFileSync(file, lines.join("\n"));
console.log(`out/_headers: Content-Security-Policy with connect-src ${connect.join(" ")}`);
