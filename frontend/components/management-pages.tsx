"use client";

import { hasOrganizationPermission } from "@/lib/auth/access";
import { AlertTriangle, ArrowUpRight, BriefcaseBusiness, CheckSquare2, ListTodo, Plus, Sparkles, UsersRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { RouteGuard } from "@/components/auth/route-guard";
import { useAuth } from "@/components/auth/auth-provider";
import { apiRequest } from "@/lib/api/client";
import { confirmAction } from "@/components/ui/action-dialog";
import {
  buttonClass,
  EmptyState,
  fieldClass,
  PageHeader,
  secondaryButtonClass,
  StatCard,
  StatusBadge,
} from "@/components/ui/page";

interface Organization {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  member_count: number;
  pending_invitation_count: number;
  artist_count: number;
  active_artist_count: number;
  inactive_artist_count: number;
  promoter_count: number;
  venue_count: number;
  contact_count: number;
  booking_count: number;
  upcoming_booking_count: number;
  confirmed_booking_count: number;
  pending_booking_count: number;
  priority_booking_count: number;
  call_sheet_count: number;
  draft_call_sheet_count: number;
  published_upcoming_call_sheet_count: number;
  confirmed_without_call_sheet_count: number;
}
interface Member {
  id: string;
  user: {
    id: string;
    email: string;
    first_name: string;
    last_name: string;
    is_active: boolean;
  };
  organization: { id: string; name: string; slug: string };
  role: string;
  is_active: boolean;
  permission_overrides?: { grant: string[]; deny: string[] };
  permissions?: string[];
  created_at: string;
}
interface Invitation {
  id: string;
  email: string;
  role: string;
  invited_by: string | null;
  created_at: string;
  expires_at: string;
  status: string;
  token?: string;
  email_delivery_status?: string;
}
interface PlatformUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  membership_count: number;
  date_joined: string;
  last_login: string | null;
  memberships?: Member[];
}
interface AuditEvent {
  id: string;
  created_at: string;
  actor: string | null;
  organization: string | null;
  action: string;
  resource_type: string;
  description: string;
  ip_address: string | null;
}

function useResource<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    if (!path) return;
    setError("");
    try {
      setData(await apiRequest<T>(path));
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to load data.",
      );
    }
  }, [path]);
  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    apiRequest<T>(path)
      .then((next) => {
        if (!cancelled) setData(next);
      })
      .catch((caught) => {
        if (!cancelled)
          setError(
            caught instanceof Error ? caught.message : "Unable to load data.",
          );
      });
    return () => {
      cancelled = true;
    };
  }, [path]);
  return { data, error, load, setData };
}

function Notice({
  message,
  error = false,
}: {
  message: string;
  error?: boolean;
}) {
  if (!message) return null;
  return (
    <p
      aria-live="polite"
      className={`rounded-md border px-4 py-3 text-sm ${error ? "border-red-900 bg-red-950 text-red-200" : "border-emerald-900 bg-emerald-950 text-emerald-200"}`}
    >
      {message}
    </p>
  );
}

function Loading() {
  return (
    <p className="py-12 text-sm text-neutral-500">Loading current data...</p>
  );
}
function WorkspaceFrame({ children }: { children: React.ReactNode }) {
  return (
    <RouteGuard portal="workspace">
      <AppShell organizationScoped>{children}</AppShell>
    </RouteGuard>
  );
}
function PlatformFrame({ children }: { children: React.ReactNode }) {
  return (
    <RouteGuard portal="platform">
      <AppShell>{children}</AppShell>
    </RouteGuard>
  );
}

export function DashboardPage() {
  const { session, activeOrganizationId } = useAuth();
  const [dashboardNow] = useState(() => Date.now());
  const [myTasks, setMyTasks] = useState<
    { id: string; title: string; status: string; due_at: string | null; is_overdue: boolean }[]
  >([]);
  const [recentActivity, setRecentActivity] = useState<
    { id: string; description: string; created_at: string; destination: string | null }[]
  >([]);
  useEffect(() => {
    if (!activeOrganizationId) return;
    if (hasOrganizationPermission(session, activeOrganizationId, "task.view"))
      void apiRequest<typeof myTasks>(
        `/api/tasks/?organization_id=${activeOrganizationId}&mine=true`,
      ).then(setMyTasks);
    if (hasOrganizationPermission(session, activeOrganizationId, "activity.view"))
      void apiRequest<typeof recentActivity>(
        `/api/activity/?organization_id=${activeOrganizationId}`,
      ).then((items) => setRecentActivity(items.slice(0, 5)));
  }, [activeOrganizationId, session]);
  const membership = session?.memberships.find(
    (item) => item.organization.id === activeOrganizationId,
  );
  const path =
    session?.user.is_superuser && !activeOrganizationId
      ? "/api/dashboard/"
      : activeOrganizationId
        ? `/api/dashboard/?organization_id=${activeOrganizationId}`
        : null;
  type Attention = {
    severity: "critical" | "high" | "normal";
    domain: string;
    title: string;
    reason: string;
    destination: string;
    due?: string;
    owner?: string;
  };
  type Dashboard = {
    mode: "platform" | "workspace";
    organization?: { id: string; name: string };
    counts: Record<string, number>;
    configuration?: Record<string, string>;
    attention: Attention[];
    today: { domain: string; title: string; destination: string; time?: string }[];
    upcoming_bookings: {
      id: string;
      reference: string;
      artist: string;
      date: string;
      days_out: number;
      venue: string;
      status: string;
      priority: string;
    }[];
  };
  const { data, error } = useResource<Dashboard>(path);
  const router = useRouter();
  const [createOpen, setCreateOpen] = useState(false);
  const canCreate = (permission: string) => Boolean(session?.user.is_superuser) || hasOrganizationPermission(session, activeOrganizationId, permission);
  const quickActions = [
    ["New Booking", "/workspace/bookings/new", "booking.manage"],
    ["New Artist", "/workspace/artists/new", "artist.manage"],
    ["New Contact", "/workspace/contacts", "contact.manage"],
    ["New Task", "/workspace/tasks/new", "task.manage"],
    ["New Production Advance", "/workspace/production/new", "production.manage"],
    ["New Travel Itinerary", "/workspace/travel/new", "travel.manage"],
    ["New Release", "/workspace/music/releases/new", "music.manage"],
    ["New Campaign", "/workspace/campaigns/new", "campaign.manage"],
    ["New Document", "/workspace/documents/new", "document.manage"],
    ["New Contract", "/workspace/contracts/new", "contract.manage"],
  ].filter(([, , permission]) => canCreate(permission));
  if (membership?.role === "artist") {
    return (
      <RouteGuard portal="dashboard">
        <AppShell>
          <PageHeader eyebrow="Home" title="Artist portal" />
          <Link className={`mt-7 ${buttonClass}`} href="/artist">
            Open Artist portal
          </Link>
        </AppShell>
      </RouteGuard>
    );
  }
  const kpis = [
    ["Upcoming bookings", data?.counts.upcoming_bookings, "/workspace/bookings"],
    ["Active Clients", data?.counts.active_artists, "/workspace/artists"],
    ["Open tasks", data?.counts.open_tasks, "/workspace/tasks"],
    ["Needs attention", data?.counts.needs_attention, "#needs-attention"],
  ].filter(([, value]) => value !== undefined) as [string, number, string][];
  const todayLabel = new Intl.DateTimeFormat(undefined, { weekday: "long", day: "numeric", month: "long" }).format(new Date());
  const kpiIcons = [BriefcaseBusiness, UsersRound, ListTodo, AlertTriangle];
  return (
    <RouteGuard portal="dashboard">
      <AppShell organizationScoped={!!activeOrganizationId}>
        <section className="evolve-dashboard-hero overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)] p-6 sm:p-8">
          <div className="relative z-10 flex flex-wrap items-end justify-between gap-6">
            <div className="max-w-2xl">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-[var(--accent-strong)]"><Sparkles size={14} /> Command Center · Nasty C</div>
              <h1 className="evolve-display mt-4 text-4xl font-semibold tracking-[-0.05em] sm:text-6xl">{data?.organization?.name ?? "Evolve"}</h1>
              <p className="mt-4 max-w-xl text-sm leading-6 text-[var(--text-secondary)]">{todayLabel}</p>
            </div>
            {quickActions.length > 0 && <div className="relative"><button aria-expanded={createOpen} className={buttonClass} onClick={() => setCreateOpen((open) => !open)} type="button"><Plus size={16} /> Create something</button>{createOpen && <><button aria-label="Close create menu" className="fixed inset-0 z-10 cursor-default" onClick={() => setCreateOpen(false)} type="button" /><div className="absolute right-0 z-20 mt-2 grid min-w-64 gap-1 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-2 shadow-2xl">{quickActions.map(([label, href]) => <Link className="rounded-[var(--radius)] px-3 py-2.5 text-left text-sm hover:bg-[var(--surface-hover)]" href={href} key={href} onClick={() => setCreateOpen(false)}>{label}</Link>)}</div></>}</div>}
          </div>
          <div className="relative z-10 mt-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{kpis.map(([label, value, href], index) => { const Icon = kpiIcons[index] ?? Sparkles; return <Link className="group rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)]/80 p-4 transition hover:-translate-y-0.5 hover:border-[var(--accent)]" href={href} key={label}><div className="flex items-center justify-between"><span className="grid size-9 place-items-center rounded-[var(--radius)] bg-[var(--surface-raised)] text-[var(--accent)]"><Icon size={17} /></span><ArrowUpRight className="text-[var(--text-muted)] transition group-hover:text-[var(--accent-strong)]" size={16} /></div><p className="mt-5 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{label}</p><p className="mt-1 text-3xl font-semibold tabular-nums">{value}</p></Link>; })}</div>
        </section>
        <Notice message={error} error />
        {!data ? <div aria-label="Loading dashboard" className="mt-7 grid animate-pulse gap-6"><div className="h-64 rounded-[var(--radius-lg)] bg-[var(--surface-raised)]" /><div className="grid gap-6 lg:grid-cols-2"><div className="h-80 rounded-[var(--radius-lg)] bg-[var(--surface-raised)]" /><div className="h-80 rounded-[var(--radius-lg)] bg-[var(--surface-raised)]" /></div></div> : data.configuration ? <section className="mt-8"><div className="mb-4 flex items-end justify-between"><div><p className="evolve-eyebrow text-xs font-semibold uppercase">Platform health</p><h2 className="mt-2 text-2xl font-semibold">System configuration</h2></div></div><div className="grid gap-4 sm:grid-cols-2">{Object.entries(data.configuration).map(([key, value]) => <StatCard key={key} label={key} value={value.replaceAll("_", " ")} />)}</div></section> : <div className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(20rem,0.8fr)]">
          <section className="hidden evolve-panel overflow-hidden"><div className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--border)] px-5 py-4"><div><p className="evolve-eyebrow text-xs font-semibold uppercase">Workspace assistant</p><h2 className="mt-1 text-lg font-semibold">Turn questions into momentum</h2><p className="mt-1 text-sm text-[var(--text-muted)]">Summarize work, surface overdue tasks, or prepare a controlled task action.</p></div><Link className={secondaryButtonClass} href="/copilot">Open assistant <ArrowUpRight size={15} /></Link></div><div className="grid gap-3 p-5 sm:grid-cols-3"><div className="rounded-[var(--radius)] bg-[var(--surface-raised)] p-4"><p className="text-sm font-medium">Workspace answers</p><p className="mt-1 text-xs text-[var(--text-muted)]">Today, attention, and overdue work.</p></div><div className="rounded-[var(--radius)] bg-[var(--surface-raised)] p-4"><p className="text-sm font-medium">Task allocation</p><p className="mt-1 text-xs text-[var(--text-muted)]">Prepare actions for confirmation.</p></div><div className="rounded-[var(--radius)] bg-[var(--surface-raised)] p-4"><p className="text-sm font-medium">Mail context</p><p className="mt-1 text-xs text-[var(--text-muted)]">Available through approved connectors.</p></div></div></section>
          <section id="needs-attention" className="evolve-panel overflow-hidden"><div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4"><div><p className="evolve-eyebrow text-xs font-semibold uppercase">Priority queue</p><h2 className="mt-1 text-lg font-semibold">Needs attention</h2></div><span className="text-xs text-[var(--text-muted)]">{data.attention.filter((item) => item.due && new Date(item.due).getTime() <= dashboardNow).length ? `${data.attention.filter((item) => item.due && new Date(item.due).getTime() <= dashboardNow).length} open` : "All clear"}</span></div><div className="divide-y divide-[var(--border)]">{data.attention.filter((item) => item.due && new Date(item.due).getTime() <= dashboardNow).map((item, index) => <Link className="grid gap-3 px-5 py-4 transition hover:bg-[var(--surface-hover)] sm:grid-cols-[5.5rem_minmax(0,1fr)_auto] sm:items-center" href={item.destination} key={`${item.domain}-${item.title}-${index}`}><span className={`text-xs font-semibold uppercase ${item.severity === "critical" ? "text-red-600" : "text-[var(--accent-strong)]"}`}>{item.severity}</span><span className="min-w-0"><span className="block truncate font-medium">{item.title}</span><span className="mt-1 block text-sm text-[var(--text-muted)]">{item.domain} / {item.reason}</span></span><span className="text-xs text-[var(--text-muted)]">{item.due ? new Date(item.due).toLocaleDateString() : "Open"}</span></Link>)}{!data.attention.filter((item) => item.due && new Date(item.due).getTime() <= dashboardNow).length && <div className="px-5 py-12 text-center"><CheckSquare2 className="mx-auto text-[var(--success)]" size={24} /><p className="mt-3 font-medium">Nothing needs immediate attention</p><p className="mt-1 text-sm text-[var(--text-muted)]">Current operational checks are clear.</p></div>}</div></section>
          <section className="evolve-panel overflow-hidden"><div className="border-b border-[var(--border)] px-5 py-4"><p className="evolve-eyebrow text-xs font-semibold uppercase">Live view</p><h2 className="mt-1 text-lg font-semibold">Today</h2></div><div className="divide-y divide-[var(--border)]">{data.today.map((item) => <Link className="block px-5 py-4 transition hover:bg-[var(--surface-hover)]" href={item.destination} key={`${item.domain}-${item.title}`}><p className="font-medium">{item.title}</p><p className="mt-1 text-xs uppercase tracking-[0.1em] text-[var(--text-muted)]">{item.domain}{item.time ? ` / ${new Date(item.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : ""}</p></Link>)}{!data.today.length && <p className="px-5 py-10 text-sm text-[var(--text-muted)]">No operational events due today.</p>}</div></section>
        </div>}
        {activeOrganizationId && <div className="mt-8 grid gap-6 xl:grid-cols-[1fr_1fr_0.9fr]">
          <section className="evolve-panel overflow-hidden"><div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4"><div><p className="evolve-eyebrow text-xs font-semibold uppercase">Personal queue</p><h2 className="mt-1 text-lg font-semibold">My work</h2></div><Link className="text-sm font-medium text-[var(--accent-strong)]" href="/workspace/tasks">View all</Link></div><div className="divide-y divide-[var(--border)]">{myTasks.filter((item) => !["done", "cancelled"].includes(item.status) && item.due_at && new Date(item.due_at).getTime() <= dashboardNow).slice(0, 5).map((item) => <Link className="flex items-center justify-between gap-3 px-5 py-4 transition hover:bg-[var(--surface-hover)]" href={`/workspace/tasks/${item.id}`} key={item.id}><span className="min-w-0 truncate">{item.title}</span><span className={item.is_overdue ? "shrink-0 text-xs font-semibold text-red-600" : "shrink-0 text-xs text-[var(--text-muted)]"}>{item.is_overdue ? "Overdue" : item.status.replaceAll("_", " ")}</span></Link>)}{!myTasks.length && <p className="p-5 text-sm text-[var(--text-muted)]">No assigned tasks.</p>}</div></section>
          <section className="evolve-panel overflow-hidden"><div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4"><div><p className="evolve-eyebrow text-xs font-semibold uppercase">Pipeline</p><h2 className="mt-1 text-lg font-semibold">Upcoming bookings</h2></div><Link className="text-sm font-medium text-[var(--accent-strong)]" href="/workspace/bookings">View all</Link></div><div className="divide-y divide-[var(--border)]">{(data?.upcoming_bookings ?? []).slice(0, 5).map((item) => <Link className="grid gap-1 px-5 py-4 transition hover:bg-[var(--surface-hover)]" href={`/workspace/bookings/${item.id}`} key={item.id}><div className="flex items-center justify-between gap-3"><span className="font-medium">{item.artist}</span><span className="text-xs text-[var(--text-muted)]">{item.days_out === 0 ? "Today" : `${item.days_out}d`}</span></div><span className="text-sm text-[var(--text-muted)]">{item.venue || "Venue TBC"} · {item.status}</span></Link>)}{!data?.upcoming_bookings?.length && <p className="p-5 text-sm text-[var(--text-muted)]">No upcoming bookings.</p>}</div></section>
          <section className="evolve-panel overflow-hidden"><div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4"><div><p className="evolve-eyebrow text-xs font-semibold uppercase">Workspace pulse</p><h2 className="mt-1 text-lg font-semibold">Recent activity</h2></div><Link className="text-sm font-medium text-[var(--accent-strong)]" href="/workspace/activity">View all</Link></div><div className="divide-y divide-[var(--border)]">{recentActivity.slice(0, 5).map((item) => item.destination ? <Link className="block px-5 py-4 transition hover:bg-[var(--surface-hover)]" href={item.destination} key={item.id}><span className="block text-sm">{item.description}</span><time className="mt-1 block text-xs text-[var(--text-muted)]">{new Date(item.created_at).toLocaleString()}</time></Link> : <div className="px-5 py-4" key={item.id}><span className="block text-sm">{item.description}</span><time className="mt-1 block text-xs text-[var(--text-muted)]">{new Date(item.created_at).toLocaleString()}</time></div>)}{!recentActivity.length && <p className="p-5 text-sm text-[var(--text-muted)]">No recent activity.</p>}</div></section>
        </div>}
      </AppShell>
    </RouteGuard>
  );
}

export function WorkspaceOverviewPage() {
  const { activeOrganizationId, activeWorkspaceId, session } = useAuth();
  type WorkspaceSummary = {
    workspace: { id: string; name: string; description: string; icon: string; archived: boolean };
    open_tasks: number;
    overdue_tasks: number;
    tasks: { id: string; title: string; status: string; due_at: string | null }[];
    upcoming_bookings: { id: string; reference: string; date: string }[];
    upcoming_releases: { id: string; title: string; release_date: string }[];
    boards: { id: string; name: string; source: string }[];
    documents: { id: string; title: string; format: string | null }[];
    recent_activity: { id: string; action: string; description: string; created_at: string }[];
  };
  const path = activeWorkspaceId ? `/api/workspaces/${activeWorkspaceId}/summary/` : null;
  const { data, error } = useResource<WorkspaceSummary>(path);
  const canManage = hasOrganizationPermission(session, activeOrganizationId, "document.manage");
  const canTask = hasOrganizationPermission(session, activeOrganizationId, "task.manage");
  const canBoard = hasOrganizationPermission(session, activeOrganizationId, "organization.manage");
  const [managementMessage, setManagementMessage] = useState("");
  async function createWorkspace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeOrganizationId) return;
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const created = await apiRequest<{ id: string }>("/api/workspaces/", { method: "POST", body: JSON.stringify({ organization_id: activeOrganizationId, ...values }) });
      sessionStorage.setItem("evolve.activeWorkspaceId", created.id);
      window.location.reload();
    } catch (caught) { setManagementMessage(caught instanceof Error ? caught.message : "Unable to create Workspace."); }
  }
  async function updateWorkspaceDetails(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeWorkspaceId || !activeOrganizationId) return;
    try { await apiRequest(`/api/workspaces/${activeWorkspaceId}/`, { method: "PATCH", body: JSON.stringify({ organization_id: activeOrganizationId, ...Object.fromEntries(new FormData(event.currentTarget)) }) }); window.location.reload(); }
    catch (caught) { setManagementMessage(caught instanceof Error ? caught.message : "Unable to edit Workspace."); }
  }
  async function updateWorkspace(archived: boolean) {
    if (!activeWorkspaceId || !activeOrganizationId) return;
    if (archived && !await confirmAction("Archive this Workspace? Existing records remain readable.")) return;
    try { await apiRequest(`/api/workspaces/${activeWorkspaceId}/`, { method: "PATCH", body: JSON.stringify({ organization_id: activeOrganizationId, archived }) }); window.location.reload(); }
    catch (caught) { setManagementMessage(caught instanceof Error ? caught.message : "Unable to update Workspace."); }
  }
  if (!activeWorkspaceId) {
    return <WorkspaceFrame><PageHeader eyebrow="Workspace" title="Choose a Workspace" description="Select an active Workspace from the application context selector to see its operational home." /><EmptyState title="No Workspace selected" detail="Your organization-wide pages remain available. Choose or create a Workspace to continue." />{hasOrganizationPermission(session, activeOrganizationId, "organization.manage") && <form className="mt-6 flex max-w-2xl flex-wrap gap-2" onSubmit={(event) => void createWorkspace(event)}><input className={fieldClass + " min-w-48 flex-1"} name="name" placeholder="Workspace name" required /><input className={fieldClass + " min-w-40 flex-1"} name="slug" placeholder="workspace-slug" required /><button className={buttonClass}>Create Workspace</button></form>}{managementMessage && <Notice message={managementMessage} error />}</WorkspaceFrame>;
  }
  return <WorkspaceFrame><PageHeader eyebrow="Workspace Home" title={data?.workspace.name ?? "Workspace"} description={data?.workspace.description || "Workspace-specific boards, documents, and work."} />
    <Notice message={error} error />
    {data?.workspace.archived && <p className="mt-5 rounded-md border border-amber-800 bg-amber-950/30 p-4 text-sm text-amber-200">This Workspace is archived. It remains readable, but new operational records are disabled.</p>}
    {data ? <>
      {managementMessage && <Notice message={managementMessage} error />}
      <div className="mt-5 flex flex-wrap gap-3">{hasOrganizationPermission(session, activeOrganizationId, "organization.manage") && <><button className={secondaryButtonClass} type="button" onClick={() => void updateWorkspace(!data.workspace.archived)}>{data.workspace.archived ? "Restore Workspace" : "Archive Workspace"}</button><form className="flex flex-wrap gap-2" onSubmit={(event) => void updateWorkspaceDetails(event)}><input className={fieldClass + " max-w-48"} name="name" defaultValue={data.workspace.name} aria-label="Workspace name" required /><input className={fieldClass + " max-w-56"} name="description" defaultValue={data.workspace.description} aria-label="Workspace description" /><button className={secondaryButtonClass}>Edit Workspace</button></form><form className="flex flex-wrap gap-2" onSubmit={(event) => void createWorkspace(event)}><input className={fieldClass + " max-w-48"} name="name" placeholder="New Workspace name" required /><input className={fieldClass + " max-w-40"} name="slug" placeholder="workspace-slug" required /><button className={secondaryButtonClass}>Create Workspace</button></form></>}</div>
      <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><StatCard label="Open tasks" value={data.open_tasks} /><StatCard label="Overdue tasks" value={data.overdue_tasks} /><StatCard label="Boards" value={data.boards.length} /><StatCard label="Documents" value={data.documents.length} /></div>
      <div className="mt-7 flex flex-wrap gap-3">{canBoard && !data.workspace.archived && <Link className={buttonClass} href="/workspace/boards">New Board</Link>}{canTask && !data.workspace.archived && <Link className={secondaryButtonClass} href="/workspace/tasks/new">New Task</Link>}{canManage && !data.workspace.archived && <><Link className={secondaryButtonClass} href="/workspace/office/new">New Document</Link><Link className={secondaryButtonClass} href="/workspace/office/new?format=sheet">New Sheet</Link></>}</div>
      <div className="mt-8 grid gap-6 lg:grid-cols-2"><section className="evolve-panel p-5"><div className="flex items-center justify-between gap-3"><h2 className="font-semibold">Boards</h2><Link className="text-sm text-neutral-400" href="/workspace/boards">View all</Link></div>{data.boards.length ? <div className="mt-3 space-y-2">{data.boards.map(item => <div className="border-t border-neutral-800 pt-3" key={item.id}><p className="font-medium">{item.name}</p><p className="text-sm text-neutral-500">{item.source}</p></div>)}</div> : <EmptyState title="No boards yet" detail={canBoard ? "Create a Board to organize this Workspace." : "Ask a Workspace manager to create a Board."} />}</section>
      <section className="evolve-panel p-5"><div className="flex items-center justify-between gap-3"><h2 className="font-semibold">Tasks</h2><Link className="text-sm text-neutral-400" href="/workspace/tasks">View all</Link></div>{data.tasks.length ? <div className="mt-3 space-y-2">{data.tasks.map(item => <Link className="block border-t border-neutral-800 pt-3" href={`/workspace/tasks/${item.id}`} key={item.id}><p className="font-medium">{item.title}</p><p className="text-sm text-neutral-500">{item.status}{item.due_at ? ` · due ${new Date(item.due_at).toLocaleDateString()}` : ""}</p></Link>)}</div> : <EmptyState title="No tasks yet" detail={canTask ? "Create a task for this Workspace." : "No Workspace-linked tasks are assigned to you."} />}</section>
      <section className="evolve-panel p-5"><div className="flex items-center justify-between gap-3"><h2 className="font-semibold">Office and Documents</h2><Link className="text-sm text-neutral-400" href="/workspace/office">View Office</Link></div>{data.documents.length ? <div className="mt-3 space-y-2">{data.documents.map(item => <Link className="block border-t border-neutral-800 pt-3" href={`/workspace/office/${item.id}`} key={item.id}><p className="font-medium">{item.title}</p><p className="text-sm text-neutral-500">{item.format || "Document"}</p></Link>)}</div> : <EmptyState title="No documents yet" detail={canManage ? "Create a Workspace document or Sheet." : "No Workspace documents are available."} />}</section>
      <section className="evolve-panel p-5"><h2 className="font-semibold">Recent activity</h2>{data.recent_activity.length ? <div className="mt-3 space-y-2">{data.recent_activity.map(item => <div className="border-t border-neutral-800 pt-3" key={item.id}><p className="text-sm">{item.description}</p><p className="mt-1 text-xs text-neutral-500">{item.action} · {new Date(item.created_at).toLocaleString()}</p></div>)}</div> : <p className="mt-3 text-sm text-neutral-500">No recent Workspace activity.</p>}</section></div>
      {!data.upcoming_bookings.length && !data.upcoming_releases.length && <p className="mt-6 text-sm text-neutral-500">Upcoming bookings and releases remain organization-wide because no explicit Workspace relationship exists yet.</p>}
    </> : <Loading />}</WorkspaceFrame>;
}
export function TeamPage() {
  const { activeOrganizationId, session } = useAuth();
  const path = activeOrganizationId
    ? `/api/organizations/${activeOrganizationId}/members/`
    : null;
  const { data, error, load } = useResource<Member[]>(path);
  const [query, setQuery] = useState("");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [message, setMessage] = useState("");
  const [permissionMember, setPermissionMember] = useState<Member | null>(null);
  const [rolePermissions, setRolePermissions] = useState<{ value: string; label: string; permissions: string[] }[]>([]);
  const canManage = hasOrganizationPermission(session, activeOrganizationId, "membership.manage");
  useEffect(() => { if (canManage) void apiRequest<typeof rolePermissions>("/api/roles/").then(setRolePermissions); }, [canManage]);
  const filtered = useMemo(
    () =>
      (data ?? []).filter(
        (item) =>
          (!query ||
            `${item.user.first_name} ${item.user.last_name} ${item.user.email}`
              .toLowerCase()
              .includes(query.toLowerCase())) &&
          (!role || item.role === role) &&
          (!status || String(item.is_active) === status),
      ),
    [data, query, role, status],
  );
  async function update(item: Member, patch: Partial<Member>) {
    if (!path || !await confirmAction("Apply this membership access change?")) return;
    setMessage("");
    try {
      await apiRequest(`${path}${item.id}/`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      setMessage("Membership updated.");
      await load();
    } catch (caught) {
      setMessage(
        caught instanceof Error
          ? caught.message
          : "Unable to update membership.",
      );
    }
  }
  return (
    <WorkspaceFrame>
      <PageHeader
        eyebrow="Workspace"
        title="Team"
        description="Organization membership, roles, and access status."
      />
      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        <input
          className={fieldClass}
          placeholder="Search name or email"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          className={fieldClass}
          value={role}
          onChange={(e) => setRole(e.target.value)}
        >
          <option value="">All roles</option>
          {["owner", "admin", "manager", "member", "artist", "artist_manager", "artist_assistant", "artist_viewer"].map((value) => (
            <option key={value} title={INVITATION_ROLE_INFO[value]}>{value}</option>
          ))}
        </select>
        <select
          className={fieldClass}
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="true">Active</option>
          <option value="false">Inactive</option>
        </select>
      </div>
      <div className="mt-4">
        <Notice
          message={error || message}
          error={!!error || message.includes("cannot")}
        />
      </div>
      {!data ? (
        <Loading />
      ) : filtered.length === 0 ? (
        <div className="mt-7">
          <EmptyState
            title="No team members"
            detail="No memberships match the current filters."
          />
        </div>
      ) : (
        <div className="mt-7 overflow-x-auto rounded-md border border-neutral-800">
          <table className="w-full min-w-176 text-left text-sm">
            <thead className="bg-neutral-900 text-neutral-500">
              <tr>
                <th className="p-4">Member</th>
                <th>Role</th>
                <th>Status</th>
                <th>Joined</th>
                <th className="p-4">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr className="border-t border-neutral-800" key={item.id}>
                  <td className="p-4">
                    <p>
                      {[item.user.first_name, item.user.last_name]
                        .filter(Boolean)
                        .join(" ") || "Unnamed user"}
                    </p>
                    <p className="text-neutral-500">{item.user.email}</p>
                  </td>
                  <td>
                    {canManage ? (
                      <select
                        className={fieldClass}
                        value={item.role}
                        onChange={(e) =>
                          void update(item, { role: e.target.value })
                        }
                      >
                        {["owner", "admin", "manager", "member", "artist", "artist_manager", "artist_assistant", "artist_viewer"].map(
                          (value) => (
                            <option key={value}>{value}</option>
                          ),
                        )}
                      </select>
                    ) : (
                      item.role
                    )}
                  </td>
                  <td>
                    <StatusBadge positive={item.is_active}>
                      {item.is_active ? "Active" : "Inactive"}
                    </StatusBadge>
                  </td>
                  <td>{new Date(item.created_at).toLocaleDateString()}</td>
                  <td className="p-4">
                    {canManage && (
                      <div className="flex flex-wrap gap-2">
                        <button className={secondaryButtonClass} onClick={() => setPermissionMember(item)}>Permissions</button>
                        <button
                          className={secondaryButtonClass}
                          onClick={() => void update(item, { is_active: !item.is_active })}
                        >
                          {item.is_active ? "Deactivate" : "Activate"}
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {permissionMember && canManage && <PermissionEditor member={permissionMember} catalog={rolePermissions} onClose={() => setPermissionMember(null)} onSave={async (overrides) => { await update(permissionMember, { permission_overrides: overrides } as Partial<Member>); setPermissionMember(null); }} />}
    </WorkspaceFrame>
  );
}

function PermissionEditor({ member, catalog, onClose, onSave }: { member: Member; catalog: { value: string; label: string; permissions: string[] }[]; onClose: () => void; onSave: (overrides: { grant: string[]; deny: string[] }) => Promise<void> }) {
  const role = catalog.find((item) => item.value === member.role);
  const base = role?.permissions ?? [];
  const [selected, setSelected] = useState<string[]>(member.permissions ?? base);
  if (member.role === "owner") return <div className="mt-5 rounded-md border border-amber-700 bg-amber-50 p-4 text-sm text-amber-900">Owner access is always unrestricted. <button className="ml-3 underline" onClick={onClose}>Close</button></div>;
  const toggle = (permission: string) => setSelected((current) => current.includes(permission) ? current.filter((item) => item !== permission) : [...current, permission]);
  return <section className="mt-5 evolve-panel p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold">Access restrictions for {member.user.email}</h2><p className="mt-1 text-sm text-[var(--text-muted)]">Role: {member.role}. Changes affect server authorization and sidebar visibility.</p></div><button className={secondaryButtonClass} onClick={onClose}>Close</button></div><div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{catalog.flatMap((item) => item.permissions).filter((permission, index, all) => all.indexOf(permission) === index).map((permission) => <label className="flex items-center gap-2 text-sm" key={permission}><input checked={selected.includes(permission)} onChange={() => toggle(permission)} type="checkbox"/>{permission}</label>)}</div><button className={`mt-5 ${buttonClass}`} onClick={() => void onSave({ grant: selected.filter((item) => !base.includes(item)), deny: base.filter((item) => !selected.includes(item)) })}>Save restrictions</button></section>;
}

const INVITATION_ROLE_INFO: Record<string, string> = { owner: "Full organization access, including membership, finance, contracts, settings, and all operational records.", admin: "Organization administration, team management, branding, integrations, and broad operational access.", manager: "Day-to-day bookings, artists, venues, production, tasks, calendars, and documents; no owner controls.", member: "Standard assigned-work access to permitted bookings, tasks, calendar, documents, and team tools.", artist: "Artist-facing access to explicitly linked artist records and approved operational information.", artist_manager: "Artist team access for assigned artist records, bookings, production, and approved documents.", artist_assistant: "Limited artist support access to assigned operational work and documents.", artist_viewer: "Read-only access to explicitly linked artist information." };

export function InvitationsPage() {
  const { activeOrganizationId, session } = useAuth();
  const path = activeOrganizationId
    ? `/api/organizations/${activeOrganizationId}/invitations/`
    : null;
  const { data, error, load } = useResource<Invitation[]>(path);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [message, setMessage] = useState("");
  const [token, setToken] = useState("");
  const [inviteLink, setInviteLink] = useState("");
    const canManage = hasOrganizationPermission(session, activeOrganizationId, "membership.manage");
  async function create(event: FormEvent) {
    event.preventDefault();
    if (!path) return;
    setMessage("");
    try {
      const created = await apiRequest<Invitation>(path, {
        method: "POST",
        body: JSON.stringify({ email, role }),
      });
      setToken(created.token ?? "");
      setInviteLink(created.token ? `${window.location.origin}/invite/${created.token}` : "");
      setEmail("");
      const deliveryStatus = (created.email_delivery_status || "pending").replaceAll("_", " ");
      setMessage(
        created.email_delivery_status === "sent"
          ? "Invitation generated and email accepted for delivery. Copy the token now; it will not be shown again."
          : "Invitation generated. Email status: " + deliveryStatus + ". Copy the token now; it will not be shown again.",
      );
      await load();
    } catch (caught) {
      setMessage(
        caught instanceof Error
          ? caught.message
          : "Unable to create invitation.",
      );
    }
  }
  async function revoke(item: Invitation) {
    if (!await confirmAction("Revoke this invitation?")) return;
    try {
      await apiRequest(`/api/invitations/${item.id}/revoke/`, {
        method: "POST",
      });
      setMessage("Invitation revoked.");
      await load();
    } catch (caught) {
      setMessage(
        caught instanceof Error
          ? caught.message
          : "Unable to revoke invitation.",
      );
    }
  }
  return (
    <WorkspaceFrame>
      <PageHeader
        eyebrow="Workspace"
        title="Invitations"
        description="Seven-day invitations with transactional email delivery when a connector is configured."
      />
      {canManage && (
        <form
          className="mt-7 grid gap-3 evolve-panel p-5 sm:grid-cols-[1fr_12rem_auto]"
          onSubmit={create}
        >
          <label className="text-sm text-neutral-400">
            Email
            <input
              className={`mt-2 ${fieldClass}`}
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label className="text-sm text-neutral-400">
            <span className="flex items-center gap-2">Role {session?.user.is_superuser && <span className="group relative inline-flex size-5 cursor-help items-center justify-center rounded-full border border-[var(--border)] text-xs text-[var(--text-muted)]" aria-label="Role access information">i<span className="pointer-events-none absolute bottom-full left-0 z-40 mb-2 hidden w-72 rounded-md border border-[var(--border)] bg-[var(--surface)] p-3 text-left text-xs leading-5 text-[var(--text-primary)] shadow-xl group-hover:block">{INVITATION_ROLE_INFO[role]} Permission restrictions can be adjusted after the invitation is accepted.</span></span>}</span>
            <select
              className={`mt-2 ${fieldClass}`}
              value={role}
              onChange={(e) => setRole(e.target.value)}
            >
              {["owner", "admin", "manager", "member", "artist", "artist_manager", "artist_assistant", "artist_viewer"].map(
                (value) => (
                  <option key={value}>{value}</option>
                ),
              )}
            </select>
          </label>
          <button className={`self-end ${buttonClass}`}>Generate invite</button>
        </form>
      )}
      <div className="mt-4">
        <Notice message={error || message} error={!!error} />
        {token && (
          <div className="mt-3 grid gap-2 rounded-md border border-[var(--border)] bg-[var(--surface-raised)] p-4 text-sm">
            <span className="font-medium">Shareable invitation link</span>
            <code className="block break-all text-[var(--accent-strong)]">{inviteLink}</code>
            <button className={`justify-self-start ${secondaryButtonClass}`} onClick={() => void navigator.clipboard?.writeText(inviteLink)} type="button">Copy link</button>
            <span className="text-xs text-[var(--text-muted)]">The link expires with the invitation. Email delivery remains available when configured.</span>
          </div>
        )}
      </div>
      {!data ? (
        <Loading />
      ) : data.length === 0 ? (
        <div className="mt-7">
          <EmptyState
            title="No invitations"
            detail="No invitations have been created for this organization."
          />
        </div>
      ) : (
        <div className="mt-7 grid gap-3">
          {data.map((item) => (
            <div
              className="grid gap-3 evolve-panel p-4 sm:grid-cols-[1fr_auto_auto] sm:items-center"
              key={item.id}
            >
              <div>
                <p>{item.email}</p>
                <p className="mt-1 text-xs text-neutral-500">
                  Created {new Date(item.created_at).toLocaleDateString()} /
                  expires {new Date(item.expires_at).toLocaleDateString()}
                </p>
              </div>
              <StatusBadge positive={item.status === "pending"}>
                {item.role} / {item.status}
              </StatusBadge>
              {canManage && item.status === "pending" && (
                <button
                  className={secondaryButtonClass}
                  onClick={() => void revoke(item)}
                >
                  Revoke
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </WorkspaceFrame>
  );
}

export function OrganizationPage() {
  const { activeOrganizationId, session, refresh } = useAuth();
  const path = activeOrganizationId
    ? `/api/organizations/${activeOrganizationId}/`
    : null;
  const { data, error, load } = useResource<Organization>(path);
  const [message, setMessage] = useState("");
  const canManage = hasOrganizationPermission(session, activeOrganizationId, "organization.manage");
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!path) return;
    const element = event.currentTarget; const form = new FormData(element);
    try {
      await apiRequest(path, {
        method: "PATCH",
        body: JSON.stringify({
          name: form.get("name"),
          slug: form.get("slug"),
        }),
      });
      setMessage("Organization updated.");
      await load();
      await refresh();
    } catch (caught) {
      setMessage(
        caught instanceof Error
          ? caught.message
          : "Unable to update organization.",
      );
    }
  }
  return (
    <WorkspaceFrame>
      <PageHeader
        eyebrow="Workspace"
        title="Organization settings"
        description="Core organization identity and status."
      />
      <div className="mt-7 max-w-2xl">
        <Notice message={error || message} error={!!error} />
        {data ? (
          <form
            key={data.updated_at}
            className="mt-4 grid gap-5 evolve-panel p-6"
            onSubmit={save}
          >
            <label className="text-sm text-neutral-400">
              Name
              <input
                name="name"
                className={`mt-2 ${fieldClass}`}
                disabled={!canManage}
                defaultValue={data.name}
              />
            </label>
            <label className="text-sm text-neutral-400">
              Slug
              <input
                name="slug"
                className={`mt-2 ${fieldClass}`}
                disabled={!canManage}
                defaultValue={data.slug}
              />
            </label>
            <div>
              <StatusBadge positive={data.is_active}>
                {data.is_active ? "Active" : "Inactive"}
              </StatusBadge>
            </div>
            {canManage && <button className={buttonClass}>Save changes</button>}
          </form>
        ) : (
          <Loading />
        )}
      </div>
    </WorkspaceFrame>
  );
}

export function ProfilePage() {
  const { refresh } = useAuth();
  const { data, error, load } = useResource<{
    email: string;
    first_name: string;
    last_name: string;
    username: string | null;
    profile_image_url: string;
    memberships: Member[];
  }>("/api/profile/");
  const [message, setMessage] = useState("");
  async function uploadProfileImage(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]; if (!file) return;
    const form = new FormData(); form.set("file", file);
    try { await apiRequest("/api/profile/image/", { method: "POST", body: form }); setMessage("Profile picture uploaded securely."); await load(); await refresh(); }
    catch (caught) { setMessage(caught instanceof Error ? caught.message : "Unable to upload profile picture."); }
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const element = event.currentTarget; const form = new FormData(element);
    try {
      await apiRequest("/api/profile/", {
        method: "PATCH",
        body: JSON.stringify({
          first_name: form.get("first_name"),
          last_name: form.get("last_name"),
          username: form.get("username"),
          profile_image_url: form.get("profile_image_url"),
        }),
      });
      setMessage("Profile updated.");
      await load();
      await refresh();
    } catch (caught) {
      setMessage(
        caught instanceof Error ? caught.message : "Unable to update profile.",
      );
    }
  }
  return (
    <RouteGuard portal="dashboard">
      <AppShell>
        <PageHeader
          eyebrow="Account"
          title="Profile"
          description="Personal details and organization memberships."
        />
        <div className="mt-7 grid gap-6 lg:grid-cols-2">
          {data ? (
            <form
              key={`${data.first_name}-${data.last_name}-${data.username ?? ""}-${data.profile_image_url}`}
              className="grid gap-5 evolve-panel p-6"
              onSubmit={save}
            >
              <Notice message={error || message} error={!!error} />
              <label className="text-sm text-neutral-400">
                Email
                <input
                  className={`mt-2 ${fieldClass}`}
                  disabled
                  value={data.email}
                />
              </label>
              <label className="text-sm text-neutral-400">
                First name
                <input
                  name="first_name"
                  className={`mt-2 ${fieldClass}`}
                  defaultValue={data.first_name}
                />
              </label>
              <label className="text-sm text-neutral-400">
                Last name
                <input
                  name="last_name"
                  className={`mt-2 ${fieldClass}`}
                  defaultValue={data.last_name}
                />
              </label>
              <label className="text-sm text-neutral-400">
                Username
                <input name="username" className={`mt-2 ${fieldClass}`} defaultValue={data.username ?? ""} placeholder="your-handle" pattern="[A-Za-z0-9_.-]{3,80}" />
              </label>
              <div className="rounded-md border border-[var(--border)] bg-[var(--surface-raised)] p-4">
                <p className="text-sm font-medium text-[var(--text-primary)]">Profile picture</p>
                <p className="mt-1 text-xs text-[var(--text-muted)]">PNG, JPEG, or WebP. The file is private and stored in the configured S3 bucket.</p>
                <input className={`mt-3 ${fieldClass}`} name="profile_image_file" type="file" accept=".png,.jpg,.jpeg,.webp" onChange={uploadProfileImage} />
                {data.profile_image_url && <img alt="Profile preview" className="mt-4 size-16 rounded-full object-cover" src={data.profile_image_url + (data.profile_image_url.includes("?") ? "&" : "?") + "v=" + encodeURIComponent(data.profile_image_url)} />}
              </div>
              <label className="text-sm text-neutral-400">Fallback profile picture URL<input name="profile_image_url" type="url" className={`mt-2 ${fieldClass}`} defaultValue={data.profile_image_url.startsWith("/api/") ? "" : data.profile_image_url} placeholder="https://..." /></label>
              <button className={buttonClass}>Save profile</button>
            </form>
          ) : (
            <Loading />
          )}
          <div className="evolve-panel p-6">
            <h2 className="font-semibold">Memberships</h2>
            <div className="mt-4 grid gap-3">
              {data?.memberships.length ? (
                data.memberships.map((item) => (
                  <div
                    className="flex justify-between border-b border-neutral-800 pb-3"
                    key={item.id}
                  >
                    <span>{item.organization.name}</span>
                    <span className="capitalize text-neutral-500">
                      {item.role}
                    </span>
                  </div>
                ))
              ) : (
                <p className="text-sm text-neutral-500">
                  No active memberships.
                </p>
              )}
            </div>
          </div>
        </div>
      </AppShell>
    </RouteGuard>
  );
}

export function PlatformOverviewPage() {
  const { data, error } = useResource<Record<string, number>>(
    "/api/platform/overview/",
  );
  return (
    <PlatformFrame>
      <PageHeader
        eyebrow="Platform"
        title="Platform overview"
        description="Live platform identity and access totals."
      />
      <Notice message={error} error />
      {data ? (
        <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(data).map(([key, value]) => (
            <StatCard
              key={key}
              label={key.replaceAll("_", " ")}
              value={value}
            />
          ))}
        </div>
      ) : (
        <Loading />
      )}
    </PlatformFrame>
  );
}

export function PlatformOrganizationsPage() {
  const { data, error } = useResource<Organization[]>(
    "/api/platform/organizations/",
  );
  const [query, setQuery] = useState("");
  const filtered = (data ?? []).filter((item) =>
    `${item.name} ${item.slug}`.toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <PlatformFrame>
      <PageHeader
        eyebrow="Platform"
        title="Organizations"
        description="All active and inactive organizations."
      />
      <input
        className={`mt-6 max-w-md ${fieldClass}`}
        placeholder="Search organizations"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <Notice message={error} error />
      {!data ? (
        <Loading />
      ) : filtered.length === 0 ? (
        <div className="mt-7">
          <EmptyState
            title="No organizations"
            detail="No organizations match this search."
          />
        </div>
      ) : (
        <div className="mt-7 grid gap-3">
          {filtered.map((item) => (
            <Link
              className="grid gap-2 evolve-panel p-5 hover:border-neutral-600 sm:grid-cols-[1fr_auto_auto]"
              href={`/platform/organizations/${item.id}`}
              key={item.id}
            >
              <div>
                <p className="font-medium">{item.name}</p>
                <p className="text-sm text-neutral-500">{item.slug}</p>
              </div>
              <span>{item.member_count} members</span>
              <StatusBadge positive={item.is_active}>
                {item.is_active ? "Active" : "Inactive"}
              </StatusBadge>
            </Link>
          ))}
        </div>
      )}
    </PlatformFrame>
  );
}

export function PlatformOrganizationDetailPage({ id }: { id: string }) {
  const { data, error, load } = useResource<
    Organization & { members: Member[]; invitations: Invitation[] }
  >(`/api/platform/organizations/${id}/`);
  async function toggle() {
    if (
      !data ||
      !await confirmAction(
        `${data.is_active ? "Deactivate" : "Activate"} this organization?`,
      )
    )
      return;
    await apiRequest(`/api/platform/organizations/${id}/`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: !data.is_active }),
    });
    await load();
  }
  return (
    <PlatformFrame>
      <PageHeader
        eyebrow="Platform organization"
        title={data?.name ?? "Organization"}
        actions={
          data && (
            <button
              className={secondaryButtonClass}
              onClick={() => void toggle()}
            >
              {data.is_active ? "Deactivate" : "Activate"}
            </button>
          )
        }
      />
      <Notice message={error} error />
      {data ? (
        <div className="mt-7 grid gap-6">
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard label="Members" value={data.members.length} />
            <StatCard label="Invitations" value={data.invitations.length} />
            <StatCard
              label="Status"
              value={data.is_active ? "Active" : "Inactive"}
            />
          </div>
          <section>
            <h2 className="mb-3 font-semibold">Members</h2>
            {data.members.map((item) => (
              <div
                className="border-t border-neutral-800 py-3 text-sm"
                key={item.id}
              >
                {item.user.email}{" "}
                <span className="text-neutral-500">/ {item.role}</span>
              </div>
            ))}
          </section>
        </div>
      ) : (
        <Loading />
      )}
    </PlatformFrame>
  );
}

export function PlatformUsersPage() {
  const { data, error } = useResource<PlatformUser[]>("/api/platform/users/");
  const [query, setQuery] = useState("");
  const filtered = (data ?? []).filter((item) =>
    `${item.email} ${item.first_name} ${item.last_name}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  return (
    <PlatformFrame>
      <PageHeader
        eyebrow="Platform"
        title="Users"
        description="Identity status and organization membership totals."
      />
      <input
        className={`mt-6 max-w-md ${fieldClass}`}
        placeholder="Search users"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <Notice message={error} error />
      {!data ? (
        <Loading />
      ) : (
        <div className="mt-7 grid gap-3">
          {filtered.map((item) => (
            <Link
              className="grid gap-2 evolve-panel p-5 hover:border-neutral-600 sm:grid-cols-[1fr_auto_auto]"
              href={`/platform/users/${item.id}`}
              key={item.id}
            >
              <div>
                <p>{item.email}</p>
                <p className="text-sm text-neutral-500">
                  {[item.first_name, item.last_name]
                    .filter(Boolean)
                    .join(" ") || "No name"}
                </p>
              </div>
              <span>{item.membership_count} memberships</span>
              <StatusBadge positive={item.is_active}>
                {item.is_superuser
                  ? "Superuser"
                  : item.is_active
                    ? "Active"
                    : "Inactive"}
              </StatusBadge>
            </Link>
          ))}
        </div>
      )}
    </PlatformFrame>
  );
}

export function PlatformUserDetailPage({ id }: { id: string }) {
  const { data, error, load } = useResource<PlatformUser>(
    `/api/platform/users/${id}/`,
  );
  async function toggle() {
    if (
      !data ||
      !await confirmAction(`${data.is_active ? "Deactivate" : "Activate"} this user?`)
    )
      return;
    await apiRequest(`/api/platform/users/${id}/`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: !data.is_active }),
    });
    await load();
  }
  return (
    <PlatformFrame>
      <PageHeader
        eyebrow="Platform user"
        title={data?.email ?? "User"}
        actions={
          data && (
            <button
              className={secondaryButtonClass}
              onClick={() => void toggle()}
            >
              {data.is_active ? "Deactivate" : "Activate"}
            </button>
          )
        }
      />
      <Notice message={error} error />
      {data ? (
        <div className="mt-7 grid gap-4 sm:grid-cols-3">
          <StatCard
            label="Status"
            value={data.is_active ? "Active" : "Inactive"}
          />
          <StatCard label="Memberships" value={data.membership_count} />
          <StatCard
            label="Last login"
            value={
              data.last_login
                ? new Date(data.last_login).toLocaleDateString()
                : "Never"
            }
          />
        </div>
      ) : (
        <Loading />
      )}
    </PlatformFrame>
  );
}

export function PlatformAuditPage() {
  const { data, error } = useResource<AuditEvent[]>("/api/platform/audit/");
  return (
    <PlatformFrame>
      <PageHeader
        eyebrow="Platform"
        title="Audit"
        description="Read-only record of important access and administration mutations."
      />
      <Notice message={error} error />
      {!data ? (
        <Loading />
      ) : data.length === 0 ? (
        <div className="mt-7">
          <EmptyState
            title="No activity recorded yet"
            detail="Audited mutations will appear here."
          />
        </div>
      ) : (
        <div className="mt-7 grid gap-3">
          {data.map((item) => (
            <div
              className="evolve-panel p-4"
              key={item.id}
            >
              <div className="flex flex-wrap justify-between gap-2">
                <p className="font-medium">{item.action}</p>
                <time className="text-xs text-neutral-500">
                  {new Date(item.created_at).toLocaleString()}
                </time>
              </div>
              <p className="mt-2 text-sm text-neutral-300">
                {item.description}
              </p>
              <p className="mt-2 text-xs text-neutral-500">
                {item.actor ?? "System"} / {item.organization ?? "Platform"} /{" "}
                {item.resource_type}
              </p>
            </div>
          ))}
        </div>
      )}
    </PlatformFrame>
  );
}

export function InvitePage({ token }: { token: string }) {
  const { session, login } = useAuth();
  const router = useRouter();
  const [message, setMessage] = useState("");
  async function accept() {
    try {
      const membership = await apiRequest<Member>("/api/invitations/accept/", { method: "POST", body: JSON.stringify({ token }) });
      setMessage(`Invitation accepted for ${membership.organization.name}.`);
      router.push("/dashboard");
    } catch (caught) { setMessage(caught instanceof Error ? caught.message : "Unable to accept invitation."); }
  }
  async function signup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    if (form.get("password") !== form.get("password_confirmation")) { setMessage("Passwords do not match."); return; }
    try {
      const result = await apiRequest<{email:string}>("/api/invitations/signup/", { method: "POST", body: JSON.stringify({ token, full_name: form.get("full_name"), password: form.get("password") }) });
      await login(result.email, String(form.get("password")));
      router.push("/dashboard");
    } catch (caught) { setMessage(caught instanceof Error ? caught.message : "Unable to complete signup."); }
  }
  return <main className="grid min-h-screen place-items-center bg-[var(--background)] p-5 text-[var(--text-primary)]"><section className="w-full max-w-lg evolve-panel p-7"><p className="evolve-eyebrow text-xs font-semibold uppercase">Evolve invitation</p><h1 className="mt-3 text-3xl font-semibold">Join organization</h1><p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">Create your account with the invited email, then access your workspace immediately.</p>{message&&<p className="mt-5 text-sm text-[var(--accent-strong)]" role="status">{message}</p>}{session?<button className={`mt-6 ${buttonClass}`} onClick={()=>void accept()}>Accept invitation</button>:<form className="mt-6 grid gap-4" onSubmit={signup}><label className="text-sm">Invited email<input className={`mt-2 ${fieldClass}`} name="email" type="email" placeholder="you@example.com" required /></label><label className="text-sm">Full name<input className={`mt-2 ${fieldClass}`} name="full_name" placeholder="First and last name" required /></label><label className="text-sm">Create password<input className={`mt-2 ${fieldClass}`} name="password" type="password" minLength={12} required /></label><label className="text-sm">Confirm password<input className={`mt-2 ${fieldClass}`} name="password_confirmation" type="password" minLength={12} required /></label><button className={buttonClass}>Create account and join</button><Link className="text-center text-sm text-[var(--accent-strong)]" href={`/login?next=/invite/${encodeURIComponent(token)}`}>Already have an account? Sign in</Link></form>}</section></main>;
}
