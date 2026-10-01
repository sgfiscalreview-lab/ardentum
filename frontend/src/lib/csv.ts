/**
 * CSV serialisation with RFC 4180 quoting (no calculations).
 *
 * Spreadsheets run a cell that starts with =, +, -, @ or a tab as a formula. Text from
 * outside sources (company names from WikiRate, names in uploaded files) is written with
 * a leading apostrophe instead, which spreadsheets show as plain text. Numbers, and text
 * that is just a number such as "-1.5%", are left alone.
 */
export function toCsv(rows: (string | number | null | undefined)[][]): string {
  const cell = (v: string | number | null | undefined) => {
    if (v === null || v === undefined) return "";
    let s = String(v);
    if (typeof v === "string" && /^[=+\-@\t\r]/.test(s) && !/^[+-]?\d[\d.,]*%?$/.test(s)) s = `'${s}`;
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return rows.map((r) => r.map(cell).join(",")).join("\n") + "\n";
}
