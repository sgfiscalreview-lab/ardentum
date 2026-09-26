"use client";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, setTokenProvider, unwrap } from "./api/client";
import type { MetaOut } from "./api/types";

export interface AuthUser {
  id: string;
  email: string | null;
}

interface AuthContextValue {
  status: "loading" | "signed_out" | "signed_in";
  user: AuthUser | null;
  meta: MetaOut | null;
  mode: "dev" | "supabase" | null;
  signInDev: (email: string) => Promise<void>;
  signInPassword: (email: string, password: string) => Promise<void>;
  signUpPassword: (email: string, password: string) => Promise<{ confirmationRequired: boolean }>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const DEV_KEY = "ardentum.devSession";

interface DevSession {
  token: string;
  expiresAt: string;
  user: AuthUser;
}

function readDevSession(): DevSession | null {
  try {
    const raw = window.localStorage.getItem(DEV_KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as DevSession;
    if (new Date(s.expiresAt).getTime() <= Date.now() + 60_000) return null;
    return s;
  } catch {
    return null;
  }
}

let supabaseSingleton: SupabaseClient | null = null;
function supabaseClient(): SupabaseClient | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) return null;
  supabaseSingleton ??= createClient(url, key, { auth: { persistSession: true, autoRefreshToken: true } });
  return supabaseSingleton;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<MetaOut | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthContextValue["status"]>("loading");
  const mode = (meta?.auth_mode as "dev" | "supabase" | undefined) ?? null;

  useEffect(() => {
    let cancelled = false;
    let unsubscribe: (() => void) | undefined;
    const apply = (u: AuthUser | null) => {
      if (cancelled) return;
      setUser(u);
      setStatus(u ? "signed_in" : "signed_out");
    };
    unwrap(api.GET("/api/v1/meta"))
      .then((m) => {
        if (cancelled) return;
        setMeta(m);
        if (m.auth_mode === "dev") {
          setTokenProvider(async () => readDevSession()?.token ?? null);
          apply(readDevSession()?.user ?? null);
          return;
        }
        const sb = supabaseClient();
        if (!sb) {
          apply(null);
          return;
        }
        setTokenProvider(async () => (await sb.auth.getSession()).data.session?.access_token ?? null);
        void sb.auth.getSession().then(({ data }) => {
          const u = data.session?.user;
          apply(u ? { id: u.id, email: u.email ?? null } : null);
        });
        const { data: sub } = sb.auth.onAuthStateChange((_event, session) => {
          const u = session?.user;
          apply(u ? { id: u.id, email: u.email ?? null } : null);
        });
        unsubscribe = () => sub.subscription.unsubscribe();
      })
      .catch(() => apply(null));
    return () => {
      cancelled = true;
      unsubscribe?.();
    };
  }, []);

  const signInDev = useCallback(async (email: string) => {
    const t = await unwrap(api.POST("/api/v1/auth/dev-login", { body: { email } }));
    const session: DevSession = {
      token: t.access_token,
      expiresAt: t.expires_at,
      user: { id: t.user_id, email: t.email },
    };
    window.localStorage.setItem(DEV_KEY, JSON.stringify(session));
    setUser(session.user);
    setStatus("signed_in");
  }, []);

  const signInPassword = useCallback(async (email: string, password: string) => {
    const sb = supabaseClient();
    if (!sb) throw new Error("Sign-in is not configured for this deployment.");
    const { error } = await sb.auth.signInWithPassword({ email, password });
    if (error) throw new Error(error.message);
  }, []);

  const signUpPassword = useCallback(async (email: string, password: string) => {
    const sb = supabaseClient();
    if (!sb) throw new Error("Sign-up is not configured for this deployment.");
    const { data, error } = await sb.auth.signUp({ email, password });
    if (error) throw new Error(error.message);
    return { confirmationRequired: !data.session };
  }, []);

  const signOut = useCallback(async () => {
    if (mode === "dev") {
      window.localStorage.removeItem(DEV_KEY);
    } else {
      await supabaseClient()?.auth.signOut();
    }
    setUser(null);
    setStatus("signed_out");
  }, [mode]);

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, meta, mode, signInDev, signInPassword, signUpPassword, signOut }),
    [status, user, meta, mode, signInDev, signInPassword, signUpPassword, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
