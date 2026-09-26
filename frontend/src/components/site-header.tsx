"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";

import { Button, cx } from "./ui";

const NAV = [
  { href: "/app", label: "Workspace" },
  { href: "/portfolios", label: "Portfolios" },
  { href: "/research", label: "Research" },
];

export function Logo() {
  return (
    <span className="flex items-center gap-2 font-semibold tracking-tight text-ink">
      <svg viewBox="0 0 24 24" className="size-5" aria-hidden>
        <path d="M3 20 L10 5 L13 11 L16 7 L21 20" fill="none" stroke="var(--accent)" strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      Ardentum
    </span>
  );
}

export function SiteHeader() {
  const pathname = usePathname();
  const { status, user, signOut } = useAuth();
  const { choice, setChoice } = useTheme();
  const next = choice === "system" ? "light" : choice === "light" ? "dark" : "system";
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur">
      <div className="mx-auto flex h-12 max-w-[1600px] items-center gap-6 px-4">
        <Link href="/" aria-label="Ardentum home">
          <Logo />
        </Link>
        <nav aria-label="Primary" className="flex items-center gap-1">
          {NAV.map((n) => {
            const active = pathname === n.href || pathname.startsWith(`${n.href}/`);
            return (
              <Link
                key={n.href}
                href={n.href}
                aria-current={active ? "page" : undefined}
                className={cx(
                  "rounded-md px-2.5 py-1.5 text-sm",
                  active ? "bg-surface-2 font-medium text-ink" : "text-ink-2 hover:text-ink",
                )}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => setChoice(next)} aria-label={`Theme: ${choice}. Switch to ${next}.`} title={`Theme: ${choice}`}>
            {choice === "dark" ? "Dark" : choice === "light" ? "Light" : "Auto"}
          </Button>
          {status === "signed_in" ? (
            <>
              <span className="hidden max-w-48 truncate text-xs text-ink-2 sm:inline" title={user?.email ?? undefined}>
                {user?.email}
              </span>
              <Button variant="secondary" size="sm" onClick={() => void signOut()}>
                Sign out
              </Button>
            </>
          ) : status === "signed_out" ? (
            <Link href={`/login?next=${encodeURIComponent(pathname)}`} className="inline-flex h-8 items-center rounded-md bg-accent px-3 text-[13px] font-medium text-white hover:bg-accent-hover">
              Sign in
            </Link>
          ) : null}
        </div>
      </div>
    </header>
  );
}
