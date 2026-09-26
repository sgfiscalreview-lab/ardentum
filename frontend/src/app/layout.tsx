import type { Metadata } from "next";
import type { ReactNode } from "react";

import { SiteFooter } from "@/components/legal";
import { SiteHeader } from "@/components/site-header";

import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: { default: "Ardentum: quantitative portfolio analysis", template: "%s · Ardentum" },
  description:
    "Construct, optimise, simulate, backtest and compare investment portfolios, with the mathematics behind every result.",
};

// Applies the saved theme before first paint to avoid a light/dark flash.
const THEME_SCRIPT = `try{var t=localStorage.getItem("ardentum.theme");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="min-h-screen">
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2">
          Skip to content
        </a>
        <Providers>
          <SiteHeader />
          <div id="main">{children}</div>
          <SiteFooter />
        </Providers>
      </body>
    </html>
  );
}
