// After a static export, writes the full Content-Security-Policy into out/_headers
// (Cloudflare Pages / Netlify). It is built here rather than kept in public/_headers
// because the addresses the page may call (the API and Supabase) are build settings.
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { contentSecurityPolicy } from "./csp-policy.mjs";

const file = join(dirname(fileURLToPath(import.meta.url)), "..", "out", "_headers");
if (!existsSync(file)) process.exit(0); // not a static export

const policy = contentSecurityPolicy(process.env);
const lines = readFileSync(file, "utf8").split("\n");
const at = lines.findIndex((l) => l.trim().startsWith("Content-Security-Policy:"));
if (at < 0) throw new Error("out/_headers has no Content-Security-Policy line to replace.");
lines[at] = `  Content-Security-Policy: ${policy}`;
writeFileSync(file, lines.join("\n"));
console.log(`out/_headers: Content-Security-Policy with ${policy.split("; ").find((d) => d.startsWith("connect-src"))}`);
