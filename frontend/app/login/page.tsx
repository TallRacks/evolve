"use client";

import { ArrowRight, LockKeyhole, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { useAuth } from "@/components/auth/auth-provider";
import { landingPath } from "@/lib/auth/access";

export default function LoginPage() {
  const router = useRouter();
  const { session, loading, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [brand, setBrand] = useState<{ brand_name?: string; logo_url?: string } | null>(null);

  useEffect(() => {
    void fetch("/api/branding/public-assets/logo/", { credentials: "same-origin" }).then((response) => response.ok ? setBrand({ logo_url: "/api/branding/public-assets/logo/" }) : undefined).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!loading && session) {
      const next = new URLSearchParams(window.location.search).get("next");
      router.replace(next?.startsWith("/invite/") ? next : landingPath(session));
    }
  }, [loading, router, session]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const next = await login(email, password);
      const destination = new URLSearchParams(window.location.search).get("next");
      router.replace(destination?.startsWith("/invite/") ? destination : landingPath(next));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to sign in.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="grid min-h-screen bg-[var(--background)] px-5 py-10 text-[var(--text-primary)] sm:place-items-center">
      <section className="evolve-panel w-full max-w-md p-7 shadow-sm sm:p-10">
        <div className="mb-10 flex items-center gap-3 text-[var(--accent-strong)]">
          {brand?.logo_url ? <img alt={brand.brand_name || "Evolve"} className="max-h-10 max-w-48 object-contain" src={brand.logo_url} /> : <><span className="grid size-10 place-items-center rounded-xl bg-[var(--accent-soft)]"><LockKeyhole aria-hidden="true" size={19} /></span><span className="text-lg font-semibold">{brand?.brand_name || "Evolve"}</span></>}
        </div>
        <p className="evolve-eyebrow text-xs font-semibold uppercase">Private operations</p>
        <h1 className="evolve-display mt-3 text-4xl font-semibold">Sign in</h1>
        <p className="mt-4 text-[var(--text-muted)]">Use your Evolve account to continue.</p>
        <form className="mt-10 grid gap-5" onSubmit={handleSubmit}>
          <label className="grid gap-2 text-sm text-[var(--text-secondary)]">
            Email address
            <input
              autoComplete="email"
              autoFocus
              className="min-h-12 rounded-[var(--radius)] border border-[var(--border-strong)] bg-[var(--background-soft)] px-4 text-[var(--text-primary)] outline-none focus:border-[var(--accent-strong)]"
              disabled={submitting}
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              value={email}
            />
          </label>
          <label className="grid gap-2 text-sm text-[var(--text-secondary)]">
            Password
            <input
              autoComplete="current-password"
              className="min-h-12 rounded-[var(--radius)] border border-[var(--border-strong)] bg-[var(--background-soft)] px-4 text-[var(--text-primary)] outline-none focus:border-[var(--accent-strong)]"
              disabled={submitting}
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </label>
          {error && (
            <p className="border-l-2 border-red-500 pl-3 text-sm text-red-300" role="alert">
              {error}
            </p>
          )}
          <button
            className="mt-2 flex min-h-12 items-center justify-center gap-2 rounded-[var(--radius)] bg-[var(--accent)] px-5 font-semibold text-[var(--accent-ink)] hover:bg-[var(--accent-strong)] disabled:cursor-wait disabled:opacity-60"
            disabled={submitting || loading}
            type="submit"
          >
            {submitting ? "Signing in..." : "Sign in"}
            {!submitting && <ArrowRight aria-hidden="true" size={18} />}
          </button>
        </form>
        <div className="mt-8 flex items-start gap-3 border-t border-[var(--border)] pt-5 text-xs leading-5 text-[var(--text-muted)]"><ShieldCheck className="mt-0.5 shrink-0 text-[var(--accent-strong)]" size={16} /> Your session is protected by Evolve secure workspace access controls.</div>
      </section>
    </main>
  );
}
