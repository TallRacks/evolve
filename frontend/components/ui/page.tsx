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
    <header className="flex flex-wrap items-end justify-between gap-5 border-b border-neutral-800 pb-7">
      <div>
        <p className="text-xs font-semibold uppercase text-amber-400">
          {eyebrow}
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-neutral-100">
          {title}
        </h1>
        {description && (
          <p className="mt-3 max-w-2xl text-sm leading-6 text-neutral-400">
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
    <div className="rounded-md border border-neutral-800 bg-neutral-900 p-5">
      <p className="text-xs font-semibold uppercase text-neutral-500">
        {label}
      </p>
      <p className="mt-3 text-2xl font-semibold text-neutral-100">{value}</p>
    </div>
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
    <div className="rounded-md border border-dashed border-neutral-700 px-6 py-12 text-center">
      <h2 className="font-semibold text-neutral-200">{title}</h2>
      <p className="mt-2 text-sm text-neutral-500">{detail}</p>
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
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${positive ? "border-emerald-800 bg-emerald-950 text-emerald-300" : "border-neutral-700 bg-neutral-800 text-neutral-300"}`}
    >
      {children}
    </span>
  );
}

export const fieldClass =
  "h-10 w-full rounded-md border border-neutral-700 bg-neutral-950 px-3 text-sm text-neutral-100 outline-none focus:border-amber-400 disabled:opacity-50";
export const buttonClass =
  "inline-flex h-10 items-center justify-center rounded-md bg-amber-400 px-4 text-sm font-semibold text-neutral-950 hover:bg-amber-300 disabled:opacity-50";
export const secondaryButtonClass =
  "inline-flex h-10 items-center justify-center rounded-md border border-neutral-700 px-4 text-sm font-medium text-neutral-200 hover:border-neutral-500";

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
