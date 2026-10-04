import { LoaderCircle } from "lucide-react";

export default function Loading() {
  return <main className="grid min-h-dvh place-items-center !bg-[#F4F1EA] px-6 text-[var(--text-primary)]"><section className="evolve-panel w-full max-w-md p-8 text-center shadow-sm"><div className="mx-auto flex h-16 max-w-56 items-center justify-center rounded-2xl bg-[var(--accent-soft)] p-3 text-[var(--accent-strong)]"><img alt="Platform logo" className="max-h-10 max-w-full object-contain" src="/api/branding/public-assets/logo/" /><LoaderCircle className="animate-spin" size={22} /></div><p className="evolve-eyebrow mt-5 text-xs font-semibold uppercase">Evolve workspace</p><h1 className="evolve-display mt-2 text-2xl font-semibold">Preparing your workspace</h1><p className="mt-3 text-sm text-[var(--text-muted)]">Loading the latest secure workspace view.</p></section></main>;
}
