import { num as plainNum, pct as plainPct } from "./format";

export { signedNum, signedPct } from "./format";

/** Formats for the research notes: as in ./format, but with a true minus sign (U+2212), as in print. */
export function num(x: number | null | undefined, digits = 2): string {
  return plainNum(x, digits).replace("-", "−");
}

export function pct(x: number | null | undefined, digits = 2): string {
  return plainPct(x, digits).replace("-", "−");
}
