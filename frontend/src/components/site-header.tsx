"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSyncExternalStore } from "react";

import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";

import { Button, buttonClass, cx, Segmented, Skeleton } from "./ui";

const NAV = [
  { href: "/app", label: "Workspace" },
  { href: "/portfolios", label: "Portfolios" },
  { href: "/research", label: "Research" },
];

const THEMES = [
  { value: "system", label: "Auto" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
] as const;

export function Logo() {
  return (
    <span className="flex items-center gap-2 text-subheadline font-semibold tracking-[-0.01em] text-ink">
      <svg viewBox="0 0 24 24" className="size-5" aria-hidden>
        <path d="M3 20 L10 5 L13 11 L16 7 L21 20" fill="none" stroke="var(--accent)" strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      Ardentum
    </span>
  );
}

function subscribeScroll(cb: () => void) {
  window.addEventListener("scroll", cb, { passive: true });
  return () => window.removeEventListener("scroll", cb);
}

/** True once the page has scrolled under the header (its scroll edge shows only then). */
function useScrolled(): boolean {
  return useSyncExternalStore(subscribeScroll, () => window.scrollY > 0, () => false);
}

export function SiteHeader() {
  const pathname = usePathname();
  const { status, user, signOut } = useAuth();
  const { choice, setChoice } = useTheme();
  const scrolled = useScrolled();
  return (
    // A translucent material that the page scrolls under. Where content meets it, a short
    // band of blur softens the edge (no ruled line), and only once content is beneath it.
    <header className="material sticky top-0 z-30 print:hidden">
      <div aria-hidden className="scroll-edge" data-on={scrolled || undefined} />
      {/* Below "sm" the menu moves to its own row so the header never exceeds the screen. */}
      <div className="mx-auto flex max-w-[100rem] flex-wrap items-center gap-x-3 px-4 sm:h-12 sm:flex-nowrap sm:gap-x-6 lg:px-6">
        <Link href="/" aria-label="Ardentum home" className="flex h-12 items-center">
          <Logo />
        </Link>
        <nav aria-label="Primary" className="order-last -mx-1 flex w-full items-center gap-1 overflow-x-auto pb-2 sm:order-none sm:mx-0 sm:w-auto sm:pb-0">
          {NAV.map((n) => {
            const active = pathname === n.href || pathname.startsWith(`${n.href}/`);
            return (
              <Link
                key={n.href}
                href={n.href}
                aria-current={active ? "page" : undefined}
                className={cx(
                  "pressable whitespace-nowrap rounded-full px-3 py-1.5 text-footnote font-medium tracking-[0.004em]",
                  active ? "bg-surface-2 text-ink" : "text-ink-2 hover:bg-surface-2/70 hover:text-ink",
                )}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <Segmented label="Colour theme" size="xs" value={choice} onChange={setChoice} items={[...THEMES]} />
          {status === "signed_in" ? (
            <>
              <Link href="/account" className="hit hidden max-w-48 truncate text-xs text-ink-2 underline-offset-2 hover:underline sm:inline" title="Account settings">
                {user?.email ?? "Account"}
              </Link>
              <Button variant="secondary" size="sm" onClick={() => void signOut()}>
                Sign out
              </Button>
            </>
          ) : status === "signed_out" ? (
            <Link href={`/login?next=${encodeURIComponent(pathname)}`} className={buttonClass("primary", "sm")}>
              Sign in
            </Link>
          ) : (
            <Skeleton className="h-8 w-16" />
          )}
        </div>
      </div>
    </header>
  );
}
