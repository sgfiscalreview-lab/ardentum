import { createRequire } from "node:module";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

// eslint-plugin-react's "detect" setting calls a context method ESLint 10 removed, so name
// the installed React version instead.
const reactVersion = createRequire(import.meta.url)("react/package.json").version;

const config = [
  ...nextVitals,
  ...nextTs,
  { settings: { react: { version: reactVersion } } },
  { ignores: [".next/**", "node_modules/**", "src/lib/api/schema.d.ts", "playwright-report/**", "test-results/**"] },
];

export default config;
