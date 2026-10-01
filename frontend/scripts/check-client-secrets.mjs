// After a build, fails if anything secret reached the files sent to browsers: Supabase
// secret or service-role keys, OAuth client secrets, access tokens, private keys or
// database passwords. Only NEXT_PUBLIC_* settings belong in the browser, and those are
// public by design (the Supabase publishable key is protected by row-level security).
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dirs = [join(root, "out"), join(root, ".next", "static")].filter(existsSync);

const patterns = [
  ["Supabase secret key", /sb_secret_[A-Za-z0-9_-]{10,}/],
  ["Google OAuth client secret", /GOCSPX-[A-Za-z0-9_-]{10,}/],
  ["GitHub token", /\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}/],
  ["private key", /-----BEGIN [A-Z ]*PRIVATE KEY-----/],
  ["database address with a password", /postgres(?:ql)?:\/\/[^\s:/@"']+:[^\s@"'/]+@/],
];
const JWT = /eyJ[A-Za-z0-9_-]{10,}\.(eyJ[A-Za-z0-9_-]{10,})\.[A-Za-z0-9_-]{10,}/g;

function* files(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) yield* files(path);
    else if (/\.(js|html|txt|json|css|map)$/.test(name)) yield path;
  }
}

const found = [];
for (const dir of dirs) {
  for (const path of files(dir)) {
    const text = readFileSync(path, "utf8");
    for (const [what, re] of patterns) if (re.test(text)) found.push(`${what} in ${relative(root, path)}`);
    for (const m of text.matchAll(JWT)) {
      try {
        const claims = JSON.parse(Buffer.from(m[1], "base64url").toString("utf8"));
        if (claims.role === "service_role") found.push(`Supabase service-role key in ${relative(root, path)}`);
      } catch {
        // not a token
      }
    }
  }
}
if (found.length) {
  console.error("Secrets found in files sent to browsers. Remove them from NEXT_PUBLIC_* settings:\n- " + found.join("\n- "));
  process.exit(1);
}
console.log(`No secrets in ${dirs.map((d) => relative(root, d)).join(", ") || "(no build output)"}.`);
