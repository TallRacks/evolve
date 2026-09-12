"use client";

import Link from "next/link";

export function MobileCreateSheet({
  actions,
  open,
  onClose,
}: {
  actions: { title: string; destination: string }[];
  open: boolean;
  onClose: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60] bg-black/70 p-4 lg:hidden" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section aria-label="Create" aria-modal="true" className="absolute inset-x-4 bottom-4 rounded-2xl border border-neutral-700 bg-neutral-950 p-4 shadow-2xl" role="dialog">
        <div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold">Create</h2><button className="min-h-10 px-3 text-sm text-neutral-400" onClick={onClose}>Close</button></div>
        <div className="grid grid-cols-2 gap-2">{actions.map((action) => <Link className="min-h-12 rounded-xl border border-neutral-800 px-3 py-3 text-sm hover:border-amber-400" href={action.destination} key={action.destination} onClick={onClose}>{action.title.replace("Create ", "")}</Link>)}</div>
      </section>
    </div>
  );
}
