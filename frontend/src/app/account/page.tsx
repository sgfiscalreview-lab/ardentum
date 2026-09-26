"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, Callout, Card, Field, Input } from "@/components/ui";
import { api, ApiError, unwrap } from "@/lib/api/client";
import { useAuth } from "@/lib/auth";

function download(name: string, body: string) {
  const url = URL.createObjectURL(new Blob([body], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export default function AccountPage() {
  const { status, user, signOut } = useAuth();
  const router = useRouter();
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState<"export" | "delete" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  if (status !== "signed_in") {
    return (
      <main className="mx-auto max-w-xl px-4 py-12">
        <h1 className="font-display text-3xl font-semibold text-ink">Account</h1>
        {done ? (
          <Callout tone="success" title="Account deleted" className="mt-6">
            {done}
          </Callout>
        ) : (
          <p className="mt-4 text-sm text-ink-2">
            <Link href="/login?next=/account" className="text-accent-ink underline underline-offset-2">
              Sign in
            </Link>{" "}
            to export or delete your data.
          </p>
        )}
      </main>
    );
  }

  const exportData = async () => {
    setBusy("export");
    setError(null);
    try {
      const data = await unwrap(api.GET("/api/v1/auth/me/export"));
      download("ardentum-account-export.json", JSON.stringify(data, null, 2));
    } catch (e) {
      setError(e instanceof ApiError || e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const deleteAccount = async () => {
    setBusy("delete");
    setError(null);
    try {
      const res = await unwrap(api.DELETE("/api/v1/auth/me"));
      setDone(res.message);
      await signOut();
      router.replace("/account");
    } catch (e) {
      setError(e instanceof ApiError || e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <main className="mx-auto max-w-xl space-y-6 px-4 py-12">
      <div>
        <h1 className="font-display text-3xl font-semibold text-ink">Account</h1>
        <p className="mt-2 text-sm text-ink-2">Signed in as {user?.email ?? "an unknown email"}.</p>
      </div>
      {error && <Callout tone="error">{error}</Callout>}
      <Card title="Download your data" subtitle="Saved portfolios, uploaded dataset details and ESG overlays, as JSON.">
        <Button onClick={() => void exportData()} busy={busy === "export"}>
          Download JSON
        </Button>
      </Card>
      <Card title="Delete your account" subtitle="Permanently deletes your portfolios, uploaded datasets, ESG overlays, background jobs and profile. This cannot be undone.">
        <div className="space-y-3">
          <Field label='Type "delete" to confirm' htmlFor="confirm-delete">
            <Input id="confirm-delete" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="off" />
          </Field>
          <Button variant="danger" onClick={() => void deleteAccount()} busy={busy === "delete"} disabled={confirm.trim().toLowerCase() !== "delete"}>
            Delete my account
          </Button>
        </div>
      </Card>
      <p className="text-xs text-muted">
        How your data is used is described in the <Link href="/privacy" className="underline underline-offset-2">Privacy Policy</Link>.
      </p>
    </main>
  );
}
