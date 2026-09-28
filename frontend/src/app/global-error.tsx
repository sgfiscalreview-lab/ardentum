"use client";

import { useEffect } from "react";

// Replaces the root layout when it fails, so it cannot rely on globals.css: colours are
// the design tokens written out (warm paper and charcoal, navy accent).
const PAPER = { bg: "#f1efea", ink: "#1d1e20", ink2: "#474744", line: "#cfcac0", accent: "#1f4f82", onAccent: "#f8f7f3" };

export default function GlobalError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="en">
      <body style={{ margin: 0, background: PAPER.bg, color: PAPER.ink, fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif" }}>
        <title>Ardentum: error</title>
        <main style={{ maxWidth: "36rem", margin: "0 auto", padding: "4rem 1rem" }}>
          <h1 style={{ fontFamily: "Georgia, 'Times New Roman', serif", fontSize: "1.875rem", fontWeight: 600, margin: 0 }}>Ardentum could not load</h1>
          <p style={{ color: PAPER.ink2, lineHeight: 1.6 }}>
            An unexpected error stopped the page. Your workspace settings are kept in this browser.
            {error.digest && ` Reference: ${error.digest}.`}
          </p>
          <button
            type="button"
            onClick={() => retry()}
            style={{ background: PAPER.accent, color: PAPER.onAccent, border: `1px solid ${PAPER.accent}`, borderRadius: 2, padding: "0.5rem 1rem", fontSize: "0.875rem", cursor: "pointer" }}
          >
            Try again
          </button>
          <p style={{ marginTop: "2rem", fontSize: "0.75rem", color: PAPER.ink2 }}>
            <a href="/terms" style={{ color: PAPER.ink2 }}>Terms of Service</a> · <a href="/privacy" style={{ color: PAPER.ink2 }}>Privacy Policy</a>
          </p>
        </main>
      </body>
    </html>
  );
}
