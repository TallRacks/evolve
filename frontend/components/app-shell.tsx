"use client";

import { Building2, ChevronDown, LayoutDashboard, LogOut, Menu, ShieldCheck, UserRound, UsersRound, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/components/auth/auth-provider";

export function AppShell({ children, organizationScoped = false }: { children: React.ReactNode; organizationScoped?: boolean }) {
  const pathname = usePathname();
  const router = useRouter();
  const { session, activeOrganizationId, selectOrganization, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const membership = session?.memberships.find((item) => item.organization.id === activeOrganizationId);
  const links = [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, show: true },
    { href: "/workspace", label: "Overview", icon: Building2, show: !!membership },
    { href: "/workspace/team", label: "Team", icon: UsersRound, show: !!membership?.permissions.includes("membership.view") },
    { href: "/workspace/invitations", label: "Invitations", icon: UsersRound, show: !!membership?.permissions.includes("membership.view") },
    { href: "/workspace/organization", label: "Organization", icon: Building2, show: !!membership },
    { href: "/platform", label: "Platform", icon: ShieldCheck, show: !!session?.user.is_superuser },
    { href: "/platform/organizations", label: "Organizations", icon: Building2, show: !!session?.user.is_superuser },
    { href: "/platform/users", label: "Users", icon: UsersRound, show: !!session?.user.is_superuser },
    { href: "/platform/audit", label: "Audit", icon: ShieldCheck, show: !!session?.user.is_superuser },
    { href: "/profile", label: "Profile", icon: UserRound, show: true },
  ];

  async function signOut() {
    setSigningOut(true);
    try { await logout(); router.replace("/login"); } finally { setSigningOut(false); }
  }

  const sidebar = (
    <aside className="flex h-full w-72 flex-col border-r border-neutral-800 bg-neutral-950">
      <div className="flex h-16 items-center justify-between border-b border-neutral-800 px-5">
        <Link className="text-lg font-semibold text-amber-400" href="/dashboard">Evolve v2</Link>
        <button className="lg:hidden" aria-label="Close navigation" onClick={() => setMenuOpen(false)}><X size={20} /></button>
      </div>
      <nav className="flex-1 overflow-y-auto p-3" aria-label="Application navigation">
        {links.filter((link) => link.show).map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`));
          return <Link aria-current={active ? "page" : undefined} className={`mb-1 flex items-center gap-3 rounded-md px-3 py-2.5 text-sm ${active ? "bg-neutral-800 text-amber-300" : "text-neutral-400 hover:bg-neutral-900 hover:text-neutral-100"}`} href={href} key={href} onClick={() => setMenuOpen(false)}><Icon size={17} /> {label}</Link>;
        })}
        <div className="mt-6 border-t border-neutral-800 pt-5">
          <p className="px-3 text-xs font-semibold uppercase text-neutral-600">Future operations</p>
          <p className="mt-3 px-3 text-sm text-neutral-600">Artists / Bookings / Music / Campaigns</p>
        </div>
      </nav>
      <button className="m-3 flex items-center gap-3 rounded-md border border-neutral-800 px-3 py-2.5 text-sm text-neutral-300 hover:border-neutral-600" disabled={signingOut} onClick={signOut}><LogOut size={17} /> {signingOut ? "Signing out..." : "Sign out"}</button>
    </aside>
  );

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <div className="fixed inset-y-0 left-0 z-30 hidden lg:block">{sidebar}</div>
      {menuOpen && <div className="fixed inset-0 z-40 lg:hidden"><button className="absolute inset-0 bg-black/70" aria-label="Close navigation" onClick={() => setMenuOpen(false)} /><div className="relative h-full">{sidebar}</div></div>}
      <div className="lg:pl-72">
        <header className="sticky top-0 z-20 flex min-h-16 items-center gap-4 border-b border-neutral-800 bg-neutral-950/95 px-4 backdrop-blur sm:px-7">
          <button className="grid size-10 place-items-center rounded-md border border-neutral-800 lg:hidden" aria-label="Open navigation" onClick={() => setMenuOpen(true)}><Menu size={19} /></button>
          <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{organizationScoped ? membership?.organization.name : "Evolve"}</p>{membership && <p className="text-xs capitalize text-neutral-500">{membership.role}</p>}</div>
          {organizationScoped && session && session.memberships.length > 1 && <label className="relative"><span className="sr-only">Current organization</span><select className="h-10 max-w-48 appearance-none rounded-md border border-neutral-700 bg-neutral-900 pl-3 pr-9 text-sm" value={activeOrganizationId ?? ""} onChange={(event) => selectOrganization(event.target.value)}>{session.memberships.map((item) => <option key={item.id} value={item.organization.id}>{item.organization.name}</option>)}</select><ChevronDown className="pointer-events-none absolute right-3 top-3" size={15} /></label>}
          <Link className="grid size-10 place-items-center rounded-md border border-neutral-800" href="/profile" aria-label="Profile"><UserRound size={18} /></Link>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-7 sm:px-7 sm:py-10">{children}</main>
      </div>
    </div>
  );
}
