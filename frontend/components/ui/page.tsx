export function PageHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description?: string; actions?: React.ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-5 border-b border-neutral-800 pb-7">
      <div>
        <p className="text-xs font-semibold uppercase text-amber-400">{eyebrow}</p>
        <h1 className="mt-2 text-3xl font-semibold text-neutral-100">{title}</h1>
        {description && <p className="mt-3 max-w-2xl text-sm leading-6 text-neutral-400">{description}</p>}
      </div>
      {actions}
    </header>
  );
}

export function StatCard({ label, value }: { label: string; value: React.ReactNode }) {
  return <div className="rounded-md border border-neutral-800 bg-neutral-900 p-5"><p className="text-xs font-semibold uppercase text-neutral-500">{label}</p><p className="mt-3 text-2xl font-semibold text-neutral-100">{value}</p></div>;
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="rounded-md border border-dashed border-neutral-700 px-6 py-12 text-center"><h2 className="font-semibold text-neutral-200">{title}</h2><p className="mt-2 text-sm text-neutral-500">{detail}</p></div>;
}

export function StatusBadge({ children, positive = false }: { children: React.ReactNode; positive?: boolean }) {
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${positive ? "border-emerald-800 bg-emerald-950 text-emerald-300" : "border-neutral-700 bg-neutral-800 text-neutral-300"}`}>{children}</span>;
}

export const fieldClass = "h-10 w-full rounded-md border border-neutral-700 bg-neutral-950 px-3 text-sm text-neutral-100 outline-none focus:border-amber-400 disabled:opacity-50";
export const buttonClass = "inline-flex h-10 items-center justify-center rounded-md bg-amber-400 px-4 text-sm font-semibold text-neutral-950 hover:bg-amber-300 disabled:opacity-50";
export const secondaryButtonClass = "inline-flex h-10 items-center justify-center rounded-md border border-neutral-700 px-4 text-sm font-medium text-neutral-200 hover:border-neutral-500";
