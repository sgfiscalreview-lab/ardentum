"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Button, Callout, Card, Field, Input } from "@/components/ui";
import { useAuth } from "@/lib/auth";

const EMAIL_AUTH = process.env.NEXT_PUBLIC_AUTH_EMAIL_ENABLED === "true";

function safeNext(n: string | null): string {
  // Only allow same-site relative paths to prevent open redirects.
  return n && n.startsWith("/") && !n.startsWith("//") ? n : "/app";
}

function LoginForm() {
  const { mode, status, signInDev, signInPassword, signUpPassword, signInOAuth } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [signup, setSignup] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  if (status === "signed_in") {
    return (
      <Callout tone="success" title="You are signed in.">
        <Link href={next} className="text-accent-ink underline underline-offset-2">
          Continue
        </Link>
      </Callout>
    );
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      if (mode === "dev") {
        await signInDev(email);
        router.push(next);
      } else if (signup) {
        const { confirmationRequired } = await signUpPassword(email, password);
        if (confirmationRequired) setInfo("Check your email to confirm your account, then sign in.");
        else router.push(next);
      } else {
        await signInPassword(email, password);
        router.push(next);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const oauth = async (provider: "google" | "github") => {
    setError(null);
    try {
      await signInOAuth(provider, next);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  if (mode === "supabase" && !EMAIL_AUTH) {
    // Email sign-in needs a custom SMTP sender; until one is configured, use OAuth only.
    return (
      <div className="space-y-3">
        <Button variant="secondary" className="w-full" onClick={() => void oauth("google")}>
          Continue with Google
        </Button>
        <Button variant="secondary" className="w-full" onClick={() => void oauth("github")}>
          Continue with GitHub
        </Button>
        {error && <Callout tone="error">{error}</Callout>}
        <p className="text-center text-[11px] text-muted">Ardentum stores only your email address and an account identifier.</p>
      </div>
    );
  }

  return (
    <form onSubmit={(e) => void submit(e)} className="space-y-4">
      {mode === "supabase" && (
        <div className="space-y-2">
          <Button type="button" variant="secondary" className="w-full" onClick={() => void oauth("google")}>
            Continue with Google
          </Button>
          <Button type="button" variant="secondary" className="w-full" onClick={() => void oauth("github")}>
            Continue with GitHub
          </Button>
          <p className="text-center text-xs text-muted">or use email</p>
        </div>
      )}
      {mode === "dev" && (
        <Callout tone="warning" title="Development sign-in">
          This server runs in development mode: any email signs you in without a password. Production deployments use Supabase authentication.
        </Callout>
      )}
      <Field label="Email" htmlFor="email">
        <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </Field>
      {mode === "supabase" && (
        <Field label="Password" htmlFor="password" hint={signup ? "At least 8 characters." : undefined}>
          <Input id="password" type="password" autoComplete={signup ? "new-password" : "current-password"} required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
      )}
      {error && <Callout tone="error">{error}</Callout>}
      {info && <Callout tone="info">{info}</Callout>}
      <Button type="submit" variant="primary" busy={busy} className="w-full" disabled={!mode}>
        {mode === "supabase" && signup ? "Create account" : "Sign in"}
      </Button>
      {mode === "supabase" && (
        <p className="text-center text-xs text-ink-2">
          {signup ? "Already have an account?" : "New to Ardentum?"}{" "}
          <button type="button" className="text-accent-ink underline underline-offset-2" onClick={() => setSignup((s) => !s)}>
            {signup ? "Sign in" : "Create an account"}
          </button>
        </p>
      )}
    </form>
  );
}

export default function LoginPage() {
  return (
    <main className="mx-auto max-w-sm px-4 py-16">
      <Card title="Sign in to Ardentum" subtitle="Save portfolios and upload your own data.">
        <Suspense>
          <LoginForm />
        </Suspense>
      </Card>
      <p className="mt-4 text-center text-xs leading-relaxed text-muted">
        By signing in you agree to the{" "}
        <Link href="/terms" className="underline underline-offset-2">
          Terms of Service
        </Link>{" "}
        and acknowledge the{" "}
        <Link href="/privacy" className="underline underline-offset-2">
          Privacy Policy
        </Link>
        .
      </p>
    </main>
  );
}
