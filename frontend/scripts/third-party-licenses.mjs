// Writes public/third-party-licenses.txt: the name, version, licence and licence text of
// every production package installed from package-lock.json (runs before `dev` and
// `build`). Fails when a package has no declared licence, or a copyleft licence in a
// package that could reach the browser, so a dependency change cannot slip one in.
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const lock = JSON.parse(readFileSync(join(root, "package-lock.json"), "utf8"));

// Used only while building on the server (image processing, browser-support data);
// never sent to visitors' browsers.
const BUILD_ONLY = /^(@img\/|sharp$|caniuse-lite$)/;
const COPYLEFT = /GPL|SSPL|BUSL|EUPL|MPL|CC-BY-NC|CC-BY-SA/i;
const LICENSE_FILE = /^(licen[cs]e|copying|notice)(\.(md|txt|markdown))?$/i;

const entries = [];
const problems = [];
for (const [path, meta] of Object.entries(lock.packages)) {
  if (!path || meta.dev || meta.devOptional) continue;
  const dir = join(root, path);
  if (!existsSync(dir)) continue; // optional package for another platform
  const name = path.slice(path.lastIndexOf("node_modules/") + "node_modules/".length);
  const license = meta.license ?? JSON.parse(readFileSync(join(dir, "package.json"), "utf8")).license;
  const buildOnly = BUILD_ONLY.test(name);
  if (!license) problems.push(`${name}: no licence declared`);
  else if (COPYLEFT.test(license) && !buildOnly) problems.push(`${name}: ${license} needs review before shipping`);
  const texts = readdirSync(dir)
    .filter((f) => LICENSE_FILE.test(f))
    .sort()
    .map((f) => readFileSync(join(dir, f), "utf8").trim());
  entries.push({ name, version: meta.version, license, buildOnly, texts });
}

if (problems.length) {
  console.error(`Third-party licence check failed:\n  ${problems.join("\n  ")}`);
  process.exit(1);
}

entries.sort((a, b) => a.name.localeCompare(b.name) || a.version.localeCompare(b.version));
const rule = "=".repeat(78);
const out = [
  "Ardentum website: third-party software notices",
  "",
  "The Ardentum website is built with the open-source packages listed below. Each is used",
  "under the licence shown, whose text follows its name where the package includes one.",
  "Packages marked [build only] run on the build server and are not sent to your browser.",
  "",
  `${entries.length} packages.`,
  "",
];
for (const e of entries) {
  out.push(rule, `${e.name} ${e.version}  (${e.license})${e.buildOnly ? "  [build only]" : ""}`, rule, "");
  if (e.texts.length) out.push(e.texts.join("\n\n"), "");
  else out.push(`No licence file is included in the package; it declares the ${e.license} licence.`, "");
}
writeFileSync(join(root, "public", "third-party-licenses.txt"), out.join("\n"));
console.log(`third-party-licenses.txt: ${entries.length} packages`);
