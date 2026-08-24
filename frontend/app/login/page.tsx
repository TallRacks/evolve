"use client";

import { ArrowRight, LockKeyhole } from "lucide-react";
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

  useEffect(() => {
    if (!loading && session) router.replace(landingPath(session));
  }, [loading, router, session]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const next = await login(email, password);
      router.replace(landingPath(next));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to sign in.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="grid min-h-screen bg-neutral-950 px-5 py-10 text-neutral-100 sm:place-items-center">
      <section className="w-full max-w-md">
        <div className="mb-10 flex items-center gap-3 text-amber-400">
          <span className="grid size-10 place-items-center border border-amber-400">
            <LockKeyhole aria-hidden="true" size={19} />
          </span>
          <span className="text-lg font-semibold">Evolve v2</span>
        </div>
        <p className="text-sm font-semibold uppercase text-amber-400">Private operations</p>
        <h1 className="mt-3 text-4xl font-semibold">Sign in</h1>
        <p className="mt-4 text-neutral-400">Use your Evolve account to continue.</p>
        <form className="mt-10 grid gap-5" onSubmit={handleSubmit}>
          <label className="grid gap-2 text-sm text-neutral-300">
            Email address
            <input
              autoComplete="email"
              autoFocus
              className="h-12 border border-neutral-700 bg-neutral-900 px-4 text-neutral-100 outline-none focus:border-amber-400"
              disabled={submitting}
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              value={email}
            />
          </label>
          <label className="grid gap-2 text-sm text-neutral-300">
            Password
            <input
              autoComplete="current-password"
              className="h-12 border border-neutral-700 bg-neutral-900 px-4 text-neutral-100 outline-none focus:border-amber-400"
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
            className="mt-2 flex h-12 items-center justify-center gap-2 bg-amber-400 px-5 font-semibold text-neutral-950 hover:bg-amber-300 disabled:cursor-wait disabled:opacity-60"
            disabled={submitting || loading}
            type="submit"
          >
            {submitting ? "Signing in..." : "Sign in"}
            {!submitting && <ArrowRight aria-hidden="true" size={18} />}
          </button>
        </form>
      </section>
    </main>
  );
}
