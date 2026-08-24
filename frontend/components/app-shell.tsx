"use client";

import Link from "next/link";
import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/components/auth/auth-provider";

interface AppShellProps {
  eyebrow: string;
  title: string;
  description: string;
  organizationScoped?: boolean;
}

const routes = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/platform", label: "Platform" },
  { href: "/workspace", label: "Workspace" },
  { href: "/artist", label: "Artist" },
];

export function AppShell({
  eyebrow,
  title,
  description,
  organizationScoped = false,
}: AppShellProps) {
  const router = useRouter();
  const { session, activeOrganizationId, selectOrganization, logout } = useAuth();
  const [signingOut, setSigningOut] = useState(false);
  const activeMembership = session?.memberships.find(
    (membership) => membership.organization.id === activeOrganizationId,
  );
  const displayName =
    [session?.user.first_name, session?.user.last_name].filter(Boolean).join(" ") ||
    session?.user.email;

  async function handleLogout() {
    setSigningOut(true);
    try {
      await logout();
      router.replace("/login");
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <main className="min-h-screen bg-neutral-950 text-neutral-100">
      <header className="border-b border-neutral-800 bg-neutral-950">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-5 px-5 py-4 sm:px-8">
          <Link className="mr-auto text-lg font-semibold text-amber-400" href="/dashboard">
            Evolve v2
          </Link>
          <nav className="flex flex-wrap gap-4 text-sm text-neutral-400" aria-label="Portal navigation">
            {routes.map((route) => (
              <Link className="hover:text-neutral-100" href={route.href} key={route.href}>
                {route.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <span className="hidden max-w-48 truncate text-sm text-neutral-400 sm:block">
              {displayName}
            </span>
            <button
              aria-label="Sign out"
              className="grid size-9 place-items-center border border-neutral-700 text-neutral-300 hover:border-amber-400 hover:text-amber-400 disabled:opacity-50"
              disabled={signingOut}
              onClick={handleLogout}
              title="Sign out"
              type="button"
            >
              <LogOut aria-hidden="true" size={17} />
            </button>
          </div>
        </div>
      </header>
      <section className="mx-auto max-w-7xl px-5 py-14 sm:px-8 sm:py-20">
        {organizationScoped && session && (
          <div className="mb-12 flex flex-wrap items-end justify-between gap-4 border-b border-neutral-800 pb-6">
            <div>
              <p className="text-xs font-semibold uppercase text-neutral-500">Current organization</p>
              <p className="mt-2 text-lg">{activeMembership?.organization.name}</p>
            </div>
            {session.memberships.length > 1 && (
              <label className="grid gap-2 text-xs font-semibold uppercase text-neutral-500">
                Switch organization
                <select
                  className="h-10 min-w-56 border border-neutral-700 bg-neutral-900 px-3 text-sm font-normal normal-case text-neutral-100"
                  onChange={(event) => selectOrganization(event.target.value)}
                  value={activeOrganizationId ?? ""}
                >
                  {session.memberships.map((membership) => (
                    <option key={membership.id} value={membership.organization.id}>
                      {membership.organization.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
        )}
        <p className="text-sm font-semibold uppercase text-amber-400">{eyebrow}</p>
        <h1 className="mt-4 max-w-3xl text-4xl font-semibold">{title}</h1>
        <p className="mt-5 max-w-2xl text-lg leading-8 text-neutral-400">{description}</p>
      </section>
    </main>
  );
}
