"use client";

import {
  BarChart3,
  Bell,
  BookOpen,
  Building2,
  CalendarDays,
  ChevronDown,
  CircleDollarSign,
  ClipboardList,
  Code2,
  ContactRound,
  FileText,
  FileSignature,
  Globe2,
  HardHat,
  LayoutDashboard,
  LogOut,
  Mail,
  MapPin,
  Menu,
  Moon,
  Sun,
  Megaphone,
  MoreHorizontal,
  Music2,
  Palette,
  Plug,
  Sparkles,
  Plane,
  Search,
  Server,
  Scale,
  ShieldCheck,
  UserRound,
  UsersRound,
  WalletCards,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { CSSProperties, useEffect, useState } from "react";
import { useAuth } from "@/components/auth/auth-provider";
import { NotificationBell } from "@/components/notification-bell";
import { MobileCreateSheet } from "@/components/mobile-create-sheet";
import { apiRequest } from "@/lib/api/client";

interface Branding {
  brand_name: string;
  logo_url: string;
  dark_logo_url?: string;
  favicon_url: string;
  mobile_icon_url: string;
  application_title: string;
  primary: string;
  accent: string;
  background: string;
  surface: string;
  text_primary: string;
  text_muted: string;
}
interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  show: boolean;
  command?: string;
}
interface NavGroup {
  label: string;
  items: NavItem[];
}
interface SearchResult {
  id: string;
  type: string;
  title: string;
  subtitle: string;
  destination: string;
  status?: string;
}
interface SearchResponse {
  groups: {
    type: string;
    label: string;
    results: SearchResult[];
    has_more: boolean;
  }[];
}
const defaultBranding: Branding = {
  brand_name: "Evolve",
  logo_url: "",
  dark_logo_url: "",
  favicon_url: "/icon",
  mobile_icon_url: "/icon",
  application_title: "Evolve",
  primary: "#8A5A00",
  accent: "#A86B00",
  background: "#F4F1EA",
  surface: "#FFFDF8",
  text_primary: "#171717",
  text_muted: "#77736B",
};

export function AppShell({
  children,
  organizationScoped = false,
}: {
  children: React.ReactNode;
  organizationScoped?: boolean;
}) {
  const pathname = usePathname();
  const router = useRouter();
  // Workspace switching is constrained by backend-authorized organization.view membership.
  const { session, activeOrganizationId, selectOrganization, logout, activeWorkspaceId, selectWorkspace } =
    useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(() => typeof window !== "undefined" && localStorage.getItem("evolve-theme") === "dark");
  const [createOpen, setCreateOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResponse>({ groups: [] });
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [searchError, setSearchError] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [workspaces, setWorkspaces] = useState<Array<{ id: string; name: string }>>([]);
  const [featureSwitches, setFeatureSwitches] = useState<Record<string, boolean>>({});
  const [brandingState, setBrandingState] = useState<{
    organizationId: string;
    data: Branding;
  } | null>(null);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>(() => {
    if (typeof window === "undefined") return {};
    try {
      return JSON.parse(
        localStorage.getItem("evolve-nav-groups") ?? "{}",
      ) as Record<string, boolean>;
    } catch {
      return {};
    }
  });
  const membership = session?.memberships.find(
    (item) => item.organization.id === activeOrganizationId,
  );
  const permissions = membership?.permissions ?? [];
  const superuser = !!session?.user.is_superuser;
  const platform = pathname.startsWith("/platform");
  const artistPortal = pathname.startsWith("/artist");
  useEffect(() => {
    document.documentElement.dataset.theme = darkMode ? "dark" : "light";
  }, [darkMode]);
  function toggleTheme() {
    const next = !darkMode;
    setDarkMode(next);
    localStorage.setItem("evolve-theme", next ? "dark" : "light");
    document.documentElement.dataset.theme = next ? "dark" : "light";
  }
  useEffect(() => {
    if (!organizationScoped || !activeOrganizationId) { queueMicrotask(() => setFeatureSwitches({})); return; }
    void apiRequest<Array<{key:string;is_enabled:boolean}>>(`/api/organizations/${activeOrganizationId}/features/`).then((items) => setFeatureSwitches(Object.fromEntries(items.map((item) => [item.key, item.is_enabled])))).catch(() => setFeatureSwitches({}));
  }, [activeOrganizationId, organizationScoped]);
  useEffect(() => {
    if (!organizationScoped || !activeOrganizationId) { queueMicrotask(() => setWorkspaces([])); return; }
    void apiRequest<Array<{ id: string; name: string }>>(`/api/workspaces/?organization_id=${activeOrganizationId}`)
      .then((next) => {
        setWorkspaces(next);
        if (activeWorkspaceId && !next.some((item) => item.id === activeWorkspaceId)) selectWorkspace(next[0]?.id ?? null);
        else if (!activeWorkspaceId && next[0]) selectWorkspace(next[0].id);
      })
      .catch(() => setWorkspaces([]));
  }, [activeOrganizationId, activeWorkspaceId, organizationScoped, selectWorkspace]);
  useEffect(() => {
    if (organizationScoped && !activeOrganizationId) return;
    let cancelled = false;
    const brandingPath = organizationScoped
      ? `/api/branding/current/?organization_id=${activeOrganizationId}`
      : "/api/branding/current/";
    apiRequest<Branding>(brandingPath)
      .then((next) => {
        if (!cancelled)
          setBrandingState({
            organizationId: organizationScoped ? activeOrganizationId ?? "" : "global",
            data: next,
          });
      })
      .catch(() => {
        if (!cancelled)
          setBrandingState({
            organizationId: organizationScoped ? activeOrganizationId ?? "" : "global",
            data: defaultBranding,
          });
      });
    return () => {
      cancelled = true;
    };
  }, [activeOrganizationId, organizationScoped]);
  useEffect(() => {
    const branding = brandingState?.data || defaultBranding;
    const href = branding.favicon_url || defaultBranding.favicon_url;
    let link = document.querySelector<HTMLLinkElement>('link[data-evolve-favicon]');
    if (!link) { link = document.createElement("link"); link.rel = "icon"; link.dataset.evolveFavicon = "true"; document.head.appendChild(link); }
    link.href = href;
    let apple = document.querySelector<HTMLLinkElement>('link[data-evolve-apple-icon]');
    if (!apple) { apple = document.createElement("link"); apple.rel = "apple-touch-icon"; apple.dataset.evolveAppleIcon = "true"; document.head.appendChild(apple); }
    apple.href = branding.mobile_icon_url || href;
    document.title = branding.application_title || branding.brand_name || "Evolve";
  }, [brandingState]);
  useEffect(() => {
    function key(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen(true);
      }
      if (event.key === "Escape") setPaletteOpen(false);
    }
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  useEffect(() => {
    const stored = sessionStorage.getItem("evolve.sidebarScrollTop");
    if (stored === null) return;
    const top = Number(stored);
    window.requestAnimationFrame(() => {
      document.querySelectorAll<HTMLElement>('nav[aria-label="Application navigation"]').forEach((nav) => {
        nav.scrollTop = Number.isFinite(top) ? top : 0;
      });
    });
  }, [pathname]);

  useEffect(() => {
    if (!paletteOpen || query.trim().length < 2) return;
    const timer = setTimeout(() => {
      const organization = activeOrganizationId
        ? `&organization_id=${activeOrganizationId}`
        : "";
      apiRequest<SearchResponse>(
        `/api/search/?q=${encodeURIComponent(query.trim())}${organization}`,
      )
        .then((response) => {
          setResults(response);
          setSearchError(false);
        })
        .catch(() => {
          setResults({ groups: [] });
          setSearchError(true);
        })
        .finally(() => setLoadingSearch(false));
    }, 250);
    return () => clearTimeout(timer);
  }, [query, paletteOpen, activeOrganizationId]);
  const branding =
    brandingState?.organizationId === (organizationScoped ? activeOrganizationId : "global")
      ? brandingState.data
      : defaultBranding;
  const can = (permission: string) =>
    (superuser && activeOrganizationId !== null) || permissions.includes(permission);
  const feature = (key: string) => featureSwitches[key] !== false;
  const organizations = superuser
    ? (session?.organizations ?? [])
    : (session?.memberships.map((item) => item.organization) ?? []);
  const groups: NavGroup[] = (() => {
    if (artistPortal)
      return [
        {
          label: "Artist portal",
          items: [
            {
              href: "/artist",
              label: "Overview",
              icon: LayoutDashboard,
              show: true,
            },
            {
              href: "/artist/production",
              label: "Production",
              icon: HardHat,
              show: true,
            },
            {
              href: "/artist/contracts",
              label: "Contracts",
              icon: FileSignature,
              show: true,
            },
            {
              href: "/artist/travel",
              label: "Travel",
              icon: Plane,
              show: true,
            },
            {
              href: "/artist/rights",
              label: "Rights",
              icon: Scale,
              show: true,
            },
            {
              href: "/notifications",
              label: "Notifications",
              icon: Bell,
              show: true,
            },
            { href: "/profile", label: "Profile", icon: UserRound, show: true },
          ],
        },
      ];
    return [
      {
        label: "Overview",
        items: [
          {
            href: "/dashboard",
            label: "Dashboard",
            icon: LayoutDashboard,
            show: true,
          },
          {
            href: "/workspace/calendar",
            label: "Calendar",
            icon: CalendarDays,
            show: can("calendar.view"),
          },
          {
            href: "/copilot",
            label: "Copilot",
            icon: Sparkles,
            show: !!session,
          },
          {
            href: "/workspace/tasks",
            label: "Tasks",
            icon: ClipboardList,
            show: can("task.view"),
          },
          {
            href: "/workspace/notifications",
            label: "Notifications",
            icon: Bell,
            show: true,
          },
          {
            href: "/workspace/activity",
            label: "Activity",
            icon: ShieldCheck,
            show: superuser && feature("activity"),
          },
          {
            href: "/workspace/reports",
            label: "Reports",
            icon: BarChart3,
            show: superuser && feature("reports"),
          },
        ],
      },
      {
        label: "Workspace",
        items: [
          { href: "/workspace", label: "Workspace home", icon: LayoutDashboard, show: superuser && feature("office") },
          { href: "/workspace/boards", label: "Boards", icon: LayoutDashboard, show: superuser && feature("boards") },
          { href: "/workspace/automations", label: "Automations", icon: Code2, show: can("organization.manage") },
          { href: "/workspace/office", label: "Office home", icon: FileText, show: superuser && feature("office") },
          { href: "/workspace/settings/trackers", label: "Bookings tracker", icon: ClipboardList, show: superuser && feature("booking-tracker") },
          { href: "/workspace/settings/booking-options", label: "Booking options", icon: ClipboardList, show: superuser && feature("booking-options") },
          { href: "/workspace/documents", label: "File uploader", icon: FileText, show: superuser && feature("file-uploader") },
          { href: "/workspace/drive", label: "Google Drive", icon: HardHat, show: can("document.view") },
          { href: "/vault", label: "Vault", icon: ShieldCheck, show: can("document.restricted.view") },
          { href: "/inbox", label: "Mailroom", icon: Mail, show: superuser && feature("mailroom") },
          { href: "/workspace/signing", label: "Signing workspace", icon: FileSignature, show: superuser && feature("signing") },
        ],
      },
      {
        label: "Artists",
        items: [
          {
            href: "/workspace/artists",
            label: "Artists",
            icon: UserRound,
            show: can("artist.view"),
          },
        ],
      },
      {
        label: "Live & operations",
        items: [
          {
            href: "/workspace/bookings",
            label: "Bookings",
            icon: BookOpen,
            show: can("booking.view"),
          },
          {
            href: "/workspace/production",
            label: "Production",
            icon: HardHat,
            show: can("production.view"),
          },
          {
            href: "/workspace/travel",
            label: "Travel",
            icon: Plane,
            show: can("travel.view"),
          },
          {
            href: "/workspace/promoters",
            label: "Promoters",
            icon: UsersRound,
            show: can("promoter.view"),
          },
          {
            href: "/workspace/venues",
            label: "Venues",
            icon: MapPin,
            show: can("venue.view"),
          },
          {
            href: "/workspace/contacts",
            label: "Contacts",
            icon: ContactRound,
            show: can("contact.view"),
          },
        ],
      },
      {
        label: "Music",
        items: [
          {
            href: "/workspace/music/releases",
            label: "Releases",
            icon: Music2,
            show: can("music.view"),
          },
          {
            href: "/workspace/music",
            label: "Music workspace",
            icon: Music2,
            show: can("music.view"),
          },
          {
            href: "/workspace/music/metadata",
            label: "Metadata",
            icon: Music2,
            show: can("music.view"),
          },
          {
            href: "/workspace/music/tracks",
            label: "Tracks",
            icon: Music2,
            show: can("music.view"),
          },
          {
            href: "/workspace/music/distribution",
            label: "Distribution readiness",
            icon: Music2,
            show: can("music.view"),
          },
          {
            href: "/workspace/campaigns",
            label: "Campaigns",
            icon: Megaphone,
            show: can("campaign.view"),
          },
        ],
      },
      {
        label: "Finance",
        items: [
          {
            href: "/workspace/finance",
            label: "Overview",
            icon: WalletCards,
            show: can("finance.view"),
          },
          {
            href: "/workspace/finance/invoices",
            label: "Invoices",
            icon: WalletCards,
            show: can("finance.view"),
          },
          {
            href: "/workspace/finance/quotes",
            label: "Quotes",
            icon: WalletCards,
            show: can("finance.view"),
          },
          {
            href: "/workspace/finance/payments",
            label: "Payments",
            icon: CircleDollarSign,
            show: can("finance.view"),
          },
          {
            href: "/workspace/finance/settings",
            label: "Company billing",
            icon: WalletCards,
            show: can("finance.manage"),
          },
          {
            href: "/workspace/finance/employee-invoices",
            label: "Employee invoices",
            icon: WalletCards,
            show: can("finance.view"),
          },
          {
            href: "/workspace/rights",
            label: "Rights",
            icon: Scale,
            show: can("rights.view"),
          },
          {
            href: "/workspace/royalties",
            label: "Royalty reporting hub",
            icon: CircleDollarSign,
            show: can("royalties.view"),
          },
          {
            href: "/workspace/royalties/statements",
            label: "Royalty Statements",
            icon: CircleDollarSign,
            show: can("royalties.view"),
          },
        ],
      },
      {
        label: "Content & records",
        items: [
          {
            href: "/workspace/contracts",
            label: "Contracts",
            icon: FileSignature,
            show: can("contract.view"),
          },
          {
            href: "/workspace/settings/templates",
            label: "Template editor",
            icon: ClipboardList,
            show: superuser && feature("template-editor"),
          },
        ],
      },
      {
        label: "Organization",
        items: [
          {
            href: "/workspace/team",
            label: "Team",
            icon: UsersRound,
            show: can("membership.view"),
          },
          {
            href: "/workspace/invitations",
            label: "Invitations",
            icon: UsersRound,
            show: can("membership.view"),
          },
          {
            href: "/workspace/organization",
            label: "Organization",
            icon: Building2,
            show: !!membership,
          },
          {
            href: "/workspace/settings/roles",
            label: "Roles & access",
            icon: UsersRound,
            show: superuser || can("membership.manage"),
          },
          {
            href: "/workspace/branding",
            label: "Branding",
            icon: Palette,
            show: can("branding.manage"),
          },
          {
            href: "/workspace/domains",
            label: "Domains",
            icon: Globe2,
            show: can("domain.manage"),
          },
          {
            href: "/developer",
            label: "Developer",
            icon: Code2,
            show: !!membership,
          },
        ],
      },
      {
        label: "Platform",
        items: [
          { href: "/platform/organizations", label: "Organizations", icon: Building2, show: superuser },
          { href: "/platform/users", label: "Users", icon: UsersRound, show: superuser },
          { href: "/platform/connectors", label: "Connectors", icon: Plug, show: superuser },
          { href: "/platform/global-branding", label: "Global branding", icon: Palette, show: superuser },
          { href: "/platform/google-workspace", label: "Google Workspace", icon: Sparkles, show: superuser },
          { href: "/platform/email-delivery", label: "Email delivery", icon: Mail, show: superuser },
          { href: "/platform/storage", label: "Storage", icon: Server, show: superuser },
          { href: "/platform/audit", label: "Audit", icon: ShieldCheck, show: superuser },
        ],
      },
      {
        label: "Account",
        items: [
          { href: "/profile", label: "Profile", icon: UserRound, show: true },
          {
            href: "/profile/security",
            label: "Security",
            icon: ShieldCheck,
            show: true,
          },
        ],
      },
    ];
  })();
  const uniqueGroups = groups.map((group) => {
    const seen = new Set<string>();
    return { ...group, items: group.items.filter((item) => {
      if (!item.show || seen.has(item.href)) return false;
      seen.add(item.href);
      return true;
    }) };
  });
  const globallyUniqueGroups = uniqueGroups.reduce<NavGroup[]>((result, group) => {
    const previous = new Set(result.flatMap((item) => item.items.map((nav) => nav.href)));
    const items = group.items.filter((item) => !previous.has(item.href));
    if (items.length) result.push({ ...group, items });
    return result;
  }, []);
  const commands = globallyUniqueGroups.flatMap((group) => group.items).filter((item) => item.show);
  const mobilePreferred = artistPortal
    ? ["Overview", "Production", "Travel", "Notifications"]
    : platform
      ? ["Organizations", "Users", "Audit"]
      : ["Dashboard", "Calendar", "Bookings", "Tasks", "Notifications"];
  const mobilePrimary = mobilePreferred
    .map((label) => commands.find((item) => item.label === label))
    .filter((item): item is NavItem => Boolean(item))
    .slice(0, 4);
  const actionCommands =
    platform || artistPortal
      ? []
      : [
          {
            title: "Create Artist",
            destination: "/workspace/artists/new",
            show: can("artist.manage"),
          },
          {
            title: "Create Booking",
            destination: "/workspace/bookings/new",
            show: can("booking.manage"),
          },
          {
            title: "Create Contact",
            destination: "/workspace/contacts",
            show: can("contact.manage"),
          },
          {
            title: "Create Task",
            destination: "/workspace/tasks/new",
            show: can("task.manage"),
          },
          {
            title: "Create Production Advance",
            destination: "/workspace/production/new",
            show: can("production.manage"),
          },
          {
            title: "Create Travel Itinerary",
            destination: "/workspace/travel/new",
            show: can("travel.manage"),
          },
          {
            title: "Create Release",
            destination: "/workspace/music/releases/new",
            show: can("music.manage"),
          },
          {
            title: "Create Track",
            destination: "/workspace/music/tracks/new",
            show: can("music.manage"),
          },
          {
            title: "Create Campaign",
            destination: "/workspace/campaigns/new",
            show: can("campaign.manage"),
          },
          {
            title: "Create Document",
            destination: "/workspace/documents/new",
            show: can("document.manage"),
          },
          {
            title: "Create Office Document",
            destination: "/workspace/office/new",
            show: can("document.manage"),
          },
          {
            title: "Create Office Sheet",
            destination: "/workspace/office/new?format=sheet",
            show: can("document.manage"),
          },
          {
            title: "Create Contract",
            destination: "/workspace/contracts/new",
            show: can("contract.manage"),
          },
          {
            title: "Create Invoice",
            destination: "/workspace/finance/invoices/new",
            show: can("finance.manage"),
          },
        ].filter((item) => item.show);
  const searchItems = results.groups.flatMap((group) => group.results);
  const paletteItems = [
    ...commands.map((item) => ({
      title: `Go to ${item.label}`,
      subtitle: "Navigation",
      destination: item.href,
    })),
    ...actionCommands.map((item) => ({
      title: item.title,
      subtitle: "Action",
      destination: item.destination,
    })),
    ...searchItems.map((item) => ({
      title: item.title,
      subtitle: `${item.type} / ${item.subtitle}`,
      destination: item.destination,
    })),
  ];
  function toggle(label: string) {
    setCollapsed((current) => {
      const next = { ...current, [label]: !current[label] };
      localStorage.setItem("evolve-nav-groups", JSON.stringify(next));
      return next;
    });
  }
  function open(destination: string) {
    setPaletteOpen(false);
    setQuery("");
    router.push(destination);
  }
  async function signOut() {
    setSigningOut(true);
    try {
      await logout();
      router.replace("/login");
    } finally {
      setSigningOut(false);
    }
  }
  const theme = {
    "--brand-primary": branding.primary,
    "--brand-accent": branding.accent,
    backgroundColor: "var(--background)",
    color: "var(--text-primary)",
  } as CSSProperties;
  const sidebar = (
    <aside
      className="evolve-sidebar flex h-full w-72 flex-col border-r"
    >
      <div className="flex h-16 items-center justify-between border-b border-white/10 px-5">
        <Link
          className="flex min-w-0 items-center gap-3 text-lg font-semibold"
          href={artistPortal ? "/artist" : "/dashboard"}
          style={{ color: branding.primary }}
        >
          {(darkMode ? branding.dark_logo_url || branding.logo_url : branding.logo_url) ? (
            <>
              <span
                aria-hidden="true"
                className="flex h-9 max-w-40 shrink-0 items-center rounded bg-contain bg-left bg-no-repeat"
                style={{ backgroundImage: `url(${darkMode ? branding.dark_logo_url || branding.logo_url : branding.logo_url})`, width: "10rem" }}
              />
              <span className="sr-only">{branding.brand_name || "Evolve"}</span>
            </>
          ) : (
            <span className="truncate">
              {organizationScoped ? branding.brand_name : "Evolve v2"}
            </span>
          )}
        </Link>
        <button
          className="lg:hidden"
          aria-label="Close navigation"
          onClick={() => setMenuOpen(false)}
        >
          <X size={20} />
        </button>
      </div>
      {session && (superuser || (organizationScoped && organizations.length > 0)) && (
        <label className="border-b border-neutral-800 p-3 lg:hidden">
          <span className="mb-2 block text-xs font-semibold uppercase text-neutral-500">Current context</span>
          <select
            className="min-h-11 w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 text-sm"
            value={activeOrganizationId ?? "platform"}
            onChange={(event) => selectOrganization(event.target.value === "platform" ? null : event.target.value)}
          >
            {superuser && <option value="platform">Platform</option>}
            {organizations.map((organization) => (
              <option key={organization.id} value={organization.id}>{organization.name}</option>
            ))}
          </select>
        </label>
      )}
      <nav
        className="flex-1 overflow-y-auto p-3"
        aria-label="Application navigation"
      >
        {globallyUniqueGroups.map((group) => {
          const visible = group.items.filter((item) => item.show);
          if (!visible.length) return null;
          return (
            <section className="mb-3" key={group.label}>
              <button
                aria-expanded={!collapsed[group.label]}
                className="flex w-full items-center justify-between px-3 py-2 text-xs font-semibold uppercase text-neutral-500"
                onClick={() => toggle(group.label)}
              >
                {group.label}
                <ChevronDown
                  className={collapsed[group.label] ? "-rotate-90" : ""}
                  size={14}
                />
              </button>
              {!collapsed[group.label] &&
                visible.map(({ href, label, icon: Icon }) => {
                  const active =
                    pathname === href ||
                    (href !== "/dashboard" && pathname.startsWith(`${href}/`));
                  return (
                    <Link
                      aria-current={active ? "page" : undefined}
                      className={`evolve-nav-item mb-1 flex items-center gap-3 rounded-[var(--radius)] px-3 py-2.5 text-sm text-[var(--text-secondary)]`}
                      href={href}
                      key={href}
                      onClick={(event) => {
                        const nav = event.currentTarget.closest("nav");
                        sessionStorage.setItem("evolve.sidebarScrollTop", String(nav?.scrollTop ?? 0));
                        setMenuOpen(false);
                      }}
                      data-active={active}
                    >
                      <Icon size={17} />
                      {label}
                    </Link>
                  );
                })}
            </section>
          );
        })}
      </nav>
      <button
        className="m-3 flex items-center gap-3 rounded-[var(--radius)] border border-[var(--border)] px-3 py-2.5 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]"
        disabled={signingOut}
        onClick={signOut}
      >
        <LogOut size={17} />
        {signingOut ? "Signing out..." : "Sign out"}
      </button>
    </aside>
  );
  return (
    <div className="evolve-app-shell min-h-screen" data-theme={darkMode ? "dark" : "light"} style={theme}>
      <div className="fixed inset-y-0 left-0 z-30 hidden lg:block">
        {sidebar}
      </div>
      {menuOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            className="absolute inset-0 bg-black/70"
            aria-label="Close navigation"
            onClick={() => setMenuOpen(false)}
          />
          <div className="relative h-full">{sidebar}</div>
        </div>
      )}
      <div className="lg:pl-72">
        <header
          className="evolve-topbar sticky top-0 z-20 flex min-h-16 items-center gap-3 border-b px-4 backdrop-blur sm:px-7"
        >
          <button
            className="grid size-10 place-items-center rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] lg:hidden"
            aria-label="Open navigation"
            onClick={() => setMenuOpen(true)}
          >
            <Menu size={19} />
          </button>
          <button
            className="pwa-search flex min-w-0 flex-1 items-center gap-3 rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-left text-sm text-neutral-400 sm:max-w-xl"
            onClick={() => setPaletteOpen(true)}
          >
            <Search size={17} />
            <span className="pwa-desktop-search-label truncate">Search or open a command</span>
            <kbd className="ml-auto hidden text-xs sm:block">⌘K</kbd>
          </button>
          {session && (superuser || (organizationScoped && organizations.length > 0)) && (
            <div className="flex items-center gap-2">
              {organizationScoped && workspaces.length > 0 && <label><span className="sr-only">Workspace</span><span className="mr-1 hidden text-xs text-neutral-500 sm:inline">Workspace</span><select aria-label="Switch Workspace" className="h-10 max-w-48 rounded-md border border-neutral-700 bg-neutral-900 px-3 text-sm" value={activeWorkspaceId ?? ""} onChange={(event) => selectWorkspace(event.target.value || null)}><option value="">All workspaces</option>{workspaces.map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}</select></label>}
            <label className="pwa-organization-select relative">
              <span className="sr-only">Organization</span><span className="mr-1 hidden text-xs text-neutral-500 sm:inline">Organization</span>
              <select
                className="h-10 max-w-48 appearance-none rounded-md border border-neutral-700 bg-neutral-900 pl-3 pr-9 text-sm"
                value={activeOrganizationId ?? "platform"}
                onChange={(event) => selectOrganization(event.target.value === "platform" ? null : event.target.value)}
              >
                {superuser && <option value="platform">Platform</option>}
                {organizations.map((organization) => (
                  <option key={organization.id} value={organization.id}>
                    {organization.name}
                  </option>
                ))}
              </select>
              <ChevronDown
                className="pointer-events-none absolute right-3 top-3"
                size={15}
              />
            </label>
            </div>
          )}
          <button aria-label={darkMode ? "Use light mode" : "Use dark mode"} className="evolve-tool-button" onClick={toggleTheme} type="button">{darkMode ? <Sun size={17}/> : <Moon size={17}/>}</button>
          <NotificationBell />
          {session && <button
            aria-label="Sign out"
            className="hidden h-10 items-center gap-2 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] px-3 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] sm:flex"
            disabled={signingOut}
            onClick={() => void signOut()}
          >
            <LogOut size={16} />
            {signingOut ? "Signing out…" : "Sign out"}
          </button>}
          <Link
            className="pwa-profile-link grid size-10 place-items-center rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)]"
            href="/profile"
            aria-label="Profile"
          >
            {session?.user.profile_image_url ? (
              <img alt="" className="size-8 rounded-full object-cover" src={session.user.profile_image_url} />
            ) : (
              <span className="grid size-8 place-items-center rounded-full bg-[var(--accent-soft)] text-xs font-semibold text-[var(--accent-strong)]">
                {(session?.user.first_name?.[0] || session?.user.email[0] || "U").toUpperCase()}
              </span>
            )}
          </Link>
        </header>
        <main className="evolve-content mx-auto max-w-[var(--content-width)] px-4 py-6 sm:px-7 sm:py-9">
          {children}
        </main>
        <nav aria-label="Installed app navigation" className="pwa-bottom-nav">
          {mobilePrimary.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`));
            return (
              <Link aria-current={active ? "page" : undefined} className={`flex min-w-0 flex-col items-center justify-center gap-1 rounded px-1 py-1 text-[0.6875rem] font-medium ${active ? "text-amber-300" : "text-neutral-400"}`} href={href} key={href}>
                <Icon aria-hidden="true" size={20} />
                <span className="max-w-full truncate">{label}</span>
              </Link>
            );
          })}
          {!platform && !artistPortal && <button className="flex min-w-0 flex-col items-center justify-center gap-1 rounded px-1 py-1 text-[0.6875rem] font-medium text-amber-300" onClick={() => setCreateOpen(true)}><span aria-hidden="true" className="text-xl leading-4">+</span><span>Create</span></button>}
          <button className="flex min-w-0 flex-col items-center justify-center gap-1 rounded px-1 py-1 text-[0.6875rem] font-medium text-neutral-400" onClick={() => setMenuOpen(true)}>
            <MoreHorizontal aria-hidden="true" size={20} />
            <span>More</span>
          </button>
        </nav>
      </div>
      <MobileCreateSheet actions={actionCommands.map(({ title, destination }) => ({ title, destination }))} open={createOpen} onClose={() => setCreateOpen(false)} />
      {paletteOpen && (
        <div
          className="fixed inset-0 z-50 flex justify-center bg-black/75 px-4 pt-[10vh]"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setPaletteOpen(false);
          }}
        >
          <section
            aria-label="Global search and command palette"
            aria-modal="true"
            className="h-fit max-h-[75vh] w-full max-w-2xl overflow-hidden rounded-md border border-neutral-700 bg-neutral-950 shadow-2xl"
            role="dialog"
          >
            <div className="flex items-center gap-3 border-b border-neutral-800 p-4">
              <Search size={18} />
              <input
                autoFocus
                aria-label="Search Evolve"
                className="min-w-0 flex-1 bg-transparent outline-none"
                placeholder="Search artists, bookings, music, rights..."
                value={query}
                onChange={(event) => {
                  const value = event.target.value;
                  setQuery(value);
                  setActiveIndex(0);
                  setSearchError(false);
                  setLoadingSearch(value.trim().length >= 2);
                  if (value.trim().length < 2) setResults({ groups: [] });
                }}
                onKeyDown={(event) => {
                  if (event.key === "ArrowDown") {
                    event.preventDefault();
                    setActiveIndex((index) =>
                      Math.min(index + 1, paletteItems.length - 1),
                    );
                  }
                  if (event.key === "ArrowUp") {
                    event.preventDefault();
                    setActiveIndex((index) => Math.max(index - 1, 0));
                  }
                  if (event.key === "Enter" && paletteItems[activeIndex])
                    open(paletteItems[activeIndex].destination);
                }}
              />
              <button
                aria-label="Close command palette"
                onClick={() => setPaletteOpen(false)}
              >
                <X size={18} />
              </button>
            </div>
            <div className="max-h-[60vh] overflow-y-auto p-2">
              {loadingSearch && (
                <p className="p-4 text-sm text-neutral-500">Searching...</p>
              )}
              {!loadingSearch && searchError && (
                <p role="alert" className="p-4 text-sm text-red-300">
                  Search is temporarily unavailable.
                </p>
              )}
              {!loadingSearch &&
                !searchError &&
                query.length >= 2 &&
                !searchItems.length && (
                  <p className="p-4 text-sm text-neutral-500">
                    No authorized results.
                  </p>
                )}
              {paletteItems.map((item, index) => (
                <button
                  className={`flex w-full items-center justify-between rounded px-3 py-3 text-left ${index === activeIndex ? "bg-neutral-800" : "hover:bg-neutral-900"}`}
                  key={`${item.destination}-${index}`}
                  onClick={() => open(item.destination)}
                >
                  <span>{item.title}</span>
                  <span className="text-xs text-neutral-500">
                    {item.subtitle}
                  </span>
                </button>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
