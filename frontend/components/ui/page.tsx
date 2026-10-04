export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-5 border-b border-[var(--border)] pb-7">
      <div>
        <p className="evolve-eyebrow text-xs font-semibold uppercase">
          {eyebrow}
        </p>
        <h1 className="evolve-display mt-2 text-3xl font-semibold tracking-[-0.03em] text-[var(--text-primary)] sm:text-4xl">
          {title}
        </h1>
        {description && (
          <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
            {description}
          </p>
        )}
      </div>
      {actions}
    </header>
  );
}

export function StatCard({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="evolve-panel evolve-panel-hover p-5">
      <p className="evolve-muted text-xs font-semibold uppercase tracking-[0.12em]">
        {label}
      </p>
      <p className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-[var(--text-primary)]">{value}</p>
    </div>
  );
}

export function WorkspaceCard({
  eyebrow,
  title,
  description,
  action,
  children,
  className = "",
}: {
  eyebrow?: string;
  title?: string;
  description?: string;
  action?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`evolve-panel overflow-hidden ${className}`}>
      {(eyebrow || title || description || action) && (
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--border)] px-5 py-4">
          <div>
            {eyebrow && <p className="evolve-eyebrow text-xs font-semibold uppercase">{eyebrow}</p>}
            {title && <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{title}</h2>}
            {description && <p className="mt-1 max-w-2xl text-sm text-[var(--text-muted)]">{description}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function EmptyState({
  title,
  detail,
}: {
  title: string;
  detail: string;
}) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-dashed border-[var(--border-strong)] bg-[var(--background-soft)] px-6 py-14 text-center">
      <h2 className="font-semibold text-[var(--text-primary)]">{title}</h2>
      <p className="mt-2 text-sm text-[var(--text-muted)]">{detail}</p>
    </div>
  );
}

export function StatusBadge({
  children,
  positive = false,
}: {
  children: React.ReactNode;
  positive?: boolean;
}) {
  const label = typeof children === "string" ? children.toLowerCase().replaceAll(" ", "_") : "";
  const tone = label.includes("enquiry") || label.includes("draft") ? "border-sky-700/40 bg-sky-50 text-sky-700" : label.includes("hold") || label.includes("pending") || label.includes("in_review") ? "border-amber-700/40 bg-amber-50 text-amber-700" : label.includes("confirmed") || label.includes("executed") || label.includes("completed") || positive ? "border-emerald-700/40 bg-emerald-50 text-emerald-700" : label.includes("declined") || label.includes("cancelled") || label.includes("failed") || label.includes("urgent") ? "border-red-700/40 bg-red-50 text-red-700" : "border-[var(--border-strong)] bg-[var(--surface-raised)] text-[var(--text-secondary)]";
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${tone}`}
    >
      {children}
    </span>
  );
}

export const fieldClass =
  "min-h-11 w-full rounded-[var(--radius)] border border-[var(--border-strong)] bg-[var(--background-soft)] px-3 text-sm text-[var(--text-primary)] outline-none transition focus:border-[var(--accent-strong)] disabled:opacity-50";
export const buttonClass =
  "inline-flex min-h-11 items-center justify-center rounded-[var(--radius)] bg-[var(--accent)] px-4 text-sm font-semibold text-[var(--accent-ink)] shadow-[0_0.5rem_1.5rem_rgb(214_179_106_/_0.12)] transition hover:bg-[var(--accent-strong)] disabled:opacity-50";
export const secondaryButtonClass =
  "inline-flex min-h-11 items-center justify-center rounded-[var(--radius)] border border-[var(--border-strong)] bg-[var(--surface)] px-4 text-sm font-medium text-[var(--text-primary)] transition hover:border-[var(--accent)] hover:bg-[var(--surface-hover)]";

export function LoadingState({
  label = "Loading current data...",
}: {
  label?: string;
}) {
  return (
    <p aria-live="polite" className="py-12 text-sm text-neutral-500">
      {label}
    </p>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <p
      role="alert"
      className="rounded-md border border-red-900 bg-red-950 px-4 py-3 text-sm text-red-200"
    >
      {message}
    </p>
  );
}

export function SectionHeader({
  title,
  action,
}: {
  title: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <h2 className="font-semibold">{title}</h2>
      {action}
    </div>
  );
}

export function Breadcrumbs({
  items,
}: {
  items: { label: string; href?: string }[];
}) {
  return (
    <nav aria-label="Breadcrumb" className="mb-4 text-sm text-neutral-500">
      <ol className="flex flex-wrap items-center gap-2">
        {items.map((item, index) => (
          <li
            className="flex items-center gap-2"
            key={`${item.label}-${index}`}
          >
            {index > 0 && <span aria-hidden="true">/</span>}
            {item.href ? (
              <a className="hover:text-neutral-200" href={item.href}>
                {item.label}
              </a>
            ) : (
              <span aria-current="page">{item.label}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
