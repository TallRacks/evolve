import { CloudOff, RotateCw } from "lucide-react";

export default function OfflinePage() {
  return (
    <main className="grid min-h-dvh place-items-center !bg-[#F4F1EA] px-6 py-12 text-[var(--text-primary)]">
      <section className="evolve-panel w-full max-w-md p-8">
        <div className="grid size-12 place-items-center rounded-2xl bg-[var(--accent-soft)] text-[var(--accent-strong)]"><CloudOff aria-hidden="true" size={25} /></div>
        <p className="evolve-eyebrow mt-7 text-xs font-semibold uppercase">Evolve mobile</p>
        <h1 className="evolve-display mt-3 text-3xl font-semibold">You are offline</h1>
        <p className="mt-4 text-sm leading-6 text-[var(--text-muted)]">Evolve could not reach the server. Private operational data is not stored for offline use. Reconnect to continue securely.</p>
        <a className="mt-8 inline-flex min-h-11 items-center gap-2 rounded-[var(--radius)] bg-[var(--accent)] px-4 text-sm font-semibold text-[var(--accent-ink)]" href="/dashboard">
          <RotateCw aria-hidden="true" size={17} /> Reload workspace
        </a>
      </section>
    </main>
  );
}
