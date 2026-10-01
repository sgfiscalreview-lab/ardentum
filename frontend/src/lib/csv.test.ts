import { describe, expect, it } from "vitest";

import { toCsv } from "./csv";

describe("toCsv", () => {
  it("quotes separators, quotes and line breaks", () => {
    expect(toCsv([["a,b", 'say "hi"', "two\nlines", null, 1.5]])).toBe('"a,b","say ""hi""","two\nlines",,1.5\n');
  });

  it("writes formula-like text as plain text", () => {
    expect(toCsv([["=HYPERLINK(\"http://x\")", "+1+cmd", "@SUM(A1)", "-2+3"]])).toBe(
      "\"'=HYPERLINK(\"\"http://x\"\")\",'+1+cmd,'@SUM(A1),'-2+3\n",
    );
  });

  it("leaves numbers alone", () => {
    expect(toCsv([[-0.25, "-1.5%", "+2", "2024-01-31"]])).toBe("-0.25,-1.5%,+2,2024-01-31\n");
  });
});
