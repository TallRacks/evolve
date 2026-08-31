import { CloudOff, RotateCw } from "lucide-react";

export default function OfflinePage() {
  return (
    <main className="grid min-h-dvh place-items-center px-6 py-12 text-neutral-100">
      <section className="w-full max-w-md border-t border-amber-400 pt-8">
        <CloudOff aria-hidden="true" className="text-amber-400" size={28} />
        <p className="mt-8 text-xs font-semibold uppercase text-neutral-500">Evolve mobile</p>
        <h1 className="evolve-display mt-3 text-3xl font-semibold">You are offline</h1>
        <p className="mt-4 text-sm leading-6 text-neutral-400">Evolve could not reach the server. Private operational data is not stored for offline use. Reconnect to continue securely.</p>
        <a className="mt-8 inline-flex h-11 items-center gap-2 rounded-md bg-amber-400 px-4 text-sm font-semibold text-neutral-950" href="/dashboard">
          <RotateCw aria-hidden="true" size={17} /> Try again
        </a>
      </section>
    </main>
  );
}
