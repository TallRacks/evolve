import Link from "next/link";
import { ArrowLeft, Compass } from "lucide-react";
import { buttonClass, secondaryButtonClass } from "@/components/ui/page";

export default function NotFound() {
  return (
    <main className="grid min-h-dvh place-items-center !bg-[#F4F1EA] px-6 py-12 text-[var(--text-primary)]">
      <section className="evolve-panel w-full max-w-lg p-8 text-center">
        <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-[var(--accent-soft)] text-[var(--accent-strong)]"><Compass aria-hidden="true" size={27} /></div>
        <p className="evolve-eyebrow mt-7 text-xs font-semibold uppercase">Evolve workspace</p>
        <h1 className="evolve-display mt-3 text-3xl font-semibold">That page is not here</h1>
        <p className="mt-4 text-sm leading-6 text-[var(--text-muted)]">The link may be outdated, or the workspace item may have moved. Return to your dashboard to continue.</p>
        <div className="mt-8 flex flex-wrap justify-center gap-3"><Link className={buttonClass} href="/dashboard">Open dashboard</Link><Link className={secondaryButtonClass} href="/workspace"><ArrowLeft size={16} /> Workspace</Link></div>
      </section>
    </main>
  );
}
