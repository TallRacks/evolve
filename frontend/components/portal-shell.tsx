import Link from "next/link";

interface PortalShellProps {
  eyebrow: string;
  title: string;
  description: string;
}

const routes = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/platform", label: "Platform" },
  { href: "/workspace", label: "Workspace" },
  { href: "/artist", label: "Artist" },
];

export function PortalShell({ eyebrow, title, description }: PortalShellProps) {
  return (
    <main className="min-h-screen bg-zinc-100 text-zinc-950">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link className="text-lg font-semibold" href="/dashboard">
            Evolve v2
          </Link>
          <nav className="flex gap-5 text-sm text-zinc-600" aria-label="Portal navigation">
            {routes.map((route) => (
              <Link className="transition-colors hover:text-zinc-950" href={route.href} key={route.href}>
                {route.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <section className="mx-auto max-w-6xl px-6 py-20">
        <p className="text-sm font-medium uppercase text-emerald-700">{eyebrow}</p>
        <h1 className="mt-4 max-w-3xl text-4xl font-semibold tracking-normal">{title}</h1>
        <p className="mt-5 max-w-2xl text-lg leading-8 text-zinc-600">{description}</p>
      </section>
    </main>
  );
}
