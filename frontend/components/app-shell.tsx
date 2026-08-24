"use client";

import {
  Building2, ChevronDown, Code2, ContactRound, Globe2, LayoutDashboard, LogOut, MapPin, Menu, Palette,
  ShieldCheck, UserRound, UsersRound, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { CSSProperties, useEffect, useState } from "react";
import { useAuth } from "@/components/auth/auth-provider";
import { apiRequest } from "@/lib/api/client";

interface Branding {
  brand_name: string; logo_url: string; primary: string; accent: string;
  background: string; surface: string; text_primary: string; text_muted: string;
}
const defaultBranding: Branding = { brand_name: "Evolve", logo_url: "", primary: "#D6A84B", accent: "#F0C96B", background: "#0A0A0A", surface: "#171717", text_primary: "#FAFAFA", text_muted: "#A3A3A3" };

export function AppShell({ children, organizationScoped = false }: { children: React.ReactNode; organizationScoped?: boolean }) {
  const pathname = usePathname(); const router = useRouter();
  const { session, activeOrganizationId, selectOrganization, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false); const [signingOut, setSigningOut] = useState(false);
  const [brandingState, setBrandingState] = useState<{ organizationId: string; data: Branding } | null>(null);
  const membership = session?.memberships.find((item) => item.organization.id === activeOrganizationId);
  useEffect(() => {
    if (!organizationScoped || !activeOrganizationId) return;
    let cancelled = false;
    apiRequest<Branding>(`/api/branding/current/?organization_id=${activeOrganizationId}`)
      .then((next) => { if (!cancelled) setBrandingState({ organizationId: activeOrganizationId, data: next }); })
      .catch(() => { if (!cancelled) setBrandingState({ organizationId: activeOrganizationId, data: defaultBranding }); });
    return () => { cancelled = true; };
  }, [activeOrganizationId, organizationScoped]);
  const branding = brandingState?.organizationId === activeOrganizationId ? brandingState.data : defaultBranding;
  const links = [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, show: true },
    { href: "/workspace", label: "Overview", icon: Building2, show: !!membership },
    { href: "/workspace/artists", label: "Artists", icon: UserRound, show: !!membership?.permissions.includes("artist.view") },
    { href: "/workspace/promoters", label: "Promoters", icon: UsersRound, show: !!membership?.permissions.includes("promoter.view") },
    { href: "/workspace/venues", label: "Venues", icon: MapPin, show: !!membership?.permissions.includes("venue.view") },
    { href: "/workspace/contacts", label: "Contacts", icon: ContactRound, show: !!membership?.permissions.includes("contact.view") },
    { href: "/workspace/team", label: "Team", icon: UsersRound, show: !!membership?.permissions.includes("membership.view") },
    { href: "/workspace/invitations", label: "Invitations", icon: UsersRound, show: !!membership?.permissions.includes("membership.view") },
    { href: "/workspace/organization", label: "Organization", icon: Building2, show: !!membership },
    { href: "/workspace/branding", label: "Branding", icon: Palette, show: !!membership?.permissions.includes("branding.manage") },
    { href: "/workspace/domains", label: "Domains", icon: Globe2, show: !!membership?.permissions.includes("domain.manage") },
    { href: "/developer", label: "Developer", icon: Code2, show: !!membership },
    { href: "/platform", label: "Platform", icon: ShieldCheck, show: !!session?.user.is_superuser },
    { href: "/platform/organizations", label: "Organizations", icon: Building2, show: !!session?.user.is_superuser },
    { href: "/platform/artists", label: "Artists", icon: UserRound, show: !!session?.user.is_superuser },
    { href: "/platform/promoters", label: "Promoters", icon: UsersRound, show: !!session?.user.is_superuser },
    { href: "/platform/venues", label: "Venues", icon: MapPin, show: !!session?.user.is_superuser },
    { href: "/platform/contacts", label: "Contacts", icon: ContactRound, show: !!session?.user.is_superuser },
    { href: "/platform/users", label: "Users", icon: UsersRound, show: !!session?.user.is_superuser },
    { href: "/platform/branding", label: "White-label", icon: Palette, show: !!session?.user.is_superuser },
    { href: "/platform/domains", label: "Domains", icon: Globe2, show: !!session?.user.is_superuser },
    { href: "/platform/audit", label: "Audit", icon: ShieldCheck, show: !!session?.user.is_superuser },
    { href: "/profile", label: "Profile", icon: UserRound, show: true },
  ];
  async function signOut() { setSigningOut(true); try { await logout(); router.replace("/login"); } finally { setSigningOut(false); } }
  const theme = { "--brand-primary": branding.primary, "--brand-accent": branding.accent, backgroundColor: branding.background, color: branding.text_primary } as CSSProperties;
  const sidebar = <aside className="flex h-full w-72 flex-col border-r border-neutral-800" style={{backgroundColor:branding.background}}>
    <div className="flex h-16 items-center justify-between border-b border-neutral-800 px-5"><Link className="flex min-w-0 items-center gap-3 text-lg font-semibold" href="/dashboard" style={{color:branding.primary}}>{branding.logo_url&&<span aria-label="Organization logo" className="size-8 shrink-0 rounded bg-contain bg-center bg-no-repeat" style={{backgroundImage:`url(${branding.logo_url})`}}/>}<span className="truncate">{organizationScoped?branding.brand_name:"Evolve v2"}</span></Link><button className="lg:hidden" aria-label="Close navigation" onClick={()=>setMenuOpen(false)}><X size={20}/></button></div>
    <nav className="flex-1 overflow-y-auto p-3" aria-label="Application navigation">{links.filter((link)=>link.show).map(({href,label,icon:Icon})=>{const active=pathname===href||(href!=="/dashboard"&&pathname.startsWith(`${href}/`));return <Link aria-current={active?"page":undefined} className={`mb-1 flex items-center gap-3 rounded-md px-3 py-2.5 text-sm ${active?"bg-neutral-800":"text-neutral-400 hover:bg-neutral-900 hover:text-neutral-100"}`} href={href} key={href} onClick={()=>setMenuOpen(false)} style={active?{color:branding.accent}:undefined}><Icon size={17}/>{label}</Link>})}</nav>
    <button className="m-3 flex items-center gap-3 rounded-md border border-neutral-800 px-3 py-2.5 text-sm text-neutral-300 hover:border-neutral-600" disabled={signingOut} onClick={signOut}><LogOut size={17}/>{signingOut?"Signing out...":"Sign out"}</button>
  </aside>;
  return <div className="min-h-screen" style={theme}><div className="fixed inset-y-0 left-0 z-30 hidden lg:block">{sidebar}</div>{menuOpen&&<div className="fixed inset-0 z-40 lg:hidden"><button className="absolute inset-0 bg-black/70" aria-label="Close navigation" onClick={()=>setMenuOpen(false)}/><div className="relative h-full">{sidebar}</div></div>}<div className="lg:pl-72"><header className="sticky top-0 z-20 flex min-h-16 items-center gap-4 border-b border-neutral-800 px-4 backdrop-blur sm:px-7" style={{backgroundColor:`${branding.background}F2`}}><button className="grid size-10 place-items-center rounded-md border border-neutral-800 lg:hidden" aria-label="Open navigation" onClick={()=>setMenuOpen(true)}><Menu size={19}/></button><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{organizationScoped?branding.brand_name:"Evolve"}</p>{membership&&<p className="text-xs capitalize" style={{color:branding.text_muted}}>{membership.role}</p>}</div>{organizationScoped&&session&&session.memberships.length>1&&<label className="relative"><span className="sr-only">Current organization</span><select className="h-10 max-w-48 appearance-none rounded-md border border-neutral-700 bg-neutral-900 pl-3 pr-9 text-sm" value={activeOrganizationId??""} onChange={(event)=>selectOrganization(event.target.value)}>{session.memberships.map((item)=><option key={item.id} value={item.organization.id}>{item.organization.name}</option>)}</select><ChevronDown className="pointer-events-none absolute right-3 top-3" size={15}/></label>}<Link className="grid size-10 place-items-center rounded-md border border-neutral-800" href="/profile" aria-label="Profile"><UserRound size={18}/></Link></header><main className="mx-auto max-w-7xl px-4 py-7 sm:px-7 sm:py-10">{children}</main></div></div>;
}
