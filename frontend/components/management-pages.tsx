"use client";

import { hasOrganizationPermission } from "@/lib/auth/access";
import { AlertTriangle, ArrowUpRight, CalendarClock, CheckSquare2, Plus } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
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
  ].filter(([, , permission]) =>
    hasOrganizationPermission(session, activeOrganizationId, permission),
  );
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
    ["Active artists", data?.counts.active_artists, "/workspace/artists"],
    ["Open tasks", data?.counts.open_tasks, "/workspace/tasks"],
    ["Needs attention", data?.counts.needs_attention, "#needs-attention"],
  ].filter(([, value]) => value !== undefined) as [string, number, string][];
  return (
    <RouteGuard portal="dashboard">
      <AppShell organizationScoped={!!activeOrganizationId}>
        <PageHeader
          eyebrow={data?.mode === "platform" ? "Platform" : "Command centre"}
          title={data?.organization?.name ?? "Dashboard"}
          description={new Intl.DateTimeFormat(undefined, {
            weekday: "long",
            day: "numeric",
            month: "long",
          }).format(new Date())}
          actions={
            quickActions.length ? (
              <details className="relative">
                <summary className={`${buttonClass} cursor-pointer list-none`}>
                  <Plus size={16} /> Create
                </summary>
                <div className="absolute right-0 z-20 mt-2 grid min-w-64 gap-1 rounded-md border border-neutral-700 bg-neutral-950 p-2 shadow-2xl">
                  {quickActions.map(([label, href]) => (
                    <Link
                      className="rounded px-3 py-2 text-sm hover:bg-neutral-800 focus:bg-neutral-800"
                      href={href}
                      key={href}
                    >
                      {label}
                    </Link>
                  ))}
                </div>
              </details>
            ) : undefined
          }
        />
        <Notice message={error} error />
        {!data ? (
          <div aria-label="Loading dashboard" className="mt-7 grid animate-pulse gap-6">
            <div className="grid gap-px overflow-hidden rounded-md border border-neutral-800 bg-neutral-800 sm:grid-cols-2 xl:grid-cols-4">
              {[1, 2, 3, 4].map((item) => (
                <div className="h-24 bg-neutral-900 p-5" key={item} />
              ))}
            </div>
            <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
              <div className="h-80 rounded-md bg-neutral-900" />
              <div className="h-80 rounded-md bg-neutral-900" />
            </div>
          </div>
        ) : (
          <>
            <div className="mt-7 grid gap-px overflow-hidden rounded-md border border-neutral-800 bg-neutral-800 sm:grid-cols-2 xl:grid-cols-4">
              {kpis.map(([label, value, href]) => (
                <Link className="group bg-neutral-950 p-5 hover:bg-neutral-900" href={href} key={label}>
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-xs font-semibold uppercase text-neutral-500">{label}</p>
                    <ArrowUpRight className="text-neutral-600 group-hover:text-amber-300" size={16} />
                  </div>
                  <p className="mt-3 text-3xl font-semibold tabular-nums">{value}</p>
                </Link>
              ))}
            </div>
            {data.configuration ? (
              <section className="mt-8">
                <h2 className="font-semibold">System configuration</h2>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  {Object.entries(data.configuration).map(([key, value]) => (
                    <StatCard key={key} label={key} value={value.replaceAll("_", " ")} />
                  ))}
                </div>
              </section>
            ) : (
              <div className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(20rem,0.8fr)]">
                <section id="needs-attention" className="rounded-md border border-neutral-800 bg-neutral-950">
                  <div className="flex items-center justify-between border-b border-neutral-800 px-5 py-4">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="text-amber-300" size={18} />
                      <h2 className="font-semibold">Needs attention</h2>
                    </div>
                    <span className="text-xs text-neutral-500">Prioritized by Evolve</span>
                  </div>
                  <div className="divide-y divide-neutral-800">
                    {data.attention.map((item, index) => (
                      <Link
                        className="grid gap-3 px-5 py-4 hover:bg-neutral-900 sm:grid-cols-[5rem_minmax(0,1fr)_auto] sm:items-center"
                        href={item.destination}
                        key={`${item.domain}-${item.title}-${index}`}
                      >
                        <span className={`text-xs font-semibold uppercase ${item.severity === "critical" ? "text-red-300" : "text-amber-300"}`}>
                          {item.severity}
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate font-medium">{item.title}</span>
                          <span className="block text-sm text-neutral-400">{item.domain} / {item.reason}</span>
                        </span>
                        <span className="text-xs text-neutral-500">
                          {item.due ? new Date(item.due).toLocaleDateString() : "Open"}
                        </span>
                      </Link>
                    ))}
                    {!data.attention.length && (
                      <div className="px-5 py-10 text-center">
                        <CheckSquare2 className="mx-auto text-emerald-300" size={24} />
                        <p className="mt-3 font-medium">Nothing needs immediate attention</p>
                        <p className="mt-1 text-sm text-neutral-500">Current operational checks are clear.</p>
                      </div>
                    )}
                  </div>
                </section>
                <section className="rounded-md border border-neutral-800 bg-neutral-950">
                  <div className="flex items-center gap-2 border-b border-neutral-800 px-5 py-4">
                    <CalendarClock className="text-neutral-400" size={18} />
                    <h2 className="font-semibold">Today</h2>
                  </div>
                  <div className="divide-y divide-neutral-800">
                    {data.today.map((item) => (
                      <Link className="block px-5 py-4 hover:bg-neutral-900" href={item.destination} key={`${item.domain}-${item.title}`}>
                        <p className="font-medium">{item.title}</p>
                        <p className="mt-1 text-xs uppercase text-neutral-500">{item.domain}{item.time ? ` / ${new Date(item.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : ""}</p>
                      </Link>
                    ))}
                    {!data.today.length && <p className="px-5 py-8 text-sm text-neutral-500">No operational events due today.</p>}
                  </div>
                </section>
              </div>
            )}
            {activeOrganizationId && (
              <div className="mt-8 grid gap-6 lg:grid-cols-2">
                <section>
                  <div className="mb-4 flex items-center justify-between"><h2 className="font-semibold">My work</h2><Link className="text-sm text-neutral-400" href="/workspace/tasks">View all</Link></div>
                  <div className="divide-y divide-neutral-800 rounded-md border border-neutral-800">
                    {myTasks.filter((item) => !["done", "cancelled"].includes(item.status)).slice(0, 5).map((item) => (
                      <Link className="flex items-center justify-between gap-3 p-4 hover:bg-neutral-900" href={`/workspace/tasks/${item.id}`} key={item.id}>
                        <span>{item.title}</span><span className={item.is_overdue ? "text-sm text-red-300" : "text-sm text-neutral-500"}>{item.is_overdue ? "Overdue" : item.status.replaceAll("_", " ")}</span>
                      </Link>
                    ))}
                    {!myTasks.length && <p className="p-5 text-sm text-neutral-500">No assigned tasks.</p>}
                  </div>
                </section>
                <section>
                  <div className="mb-4 flex items-center justify-between"><h2 className="font-semibold">Recent activity</h2><Link className="text-sm text-neutral-400" href="/workspace/activity">View all</Link></div>
                  <div className="divide-y divide-neutral-800 rounded-md border border-neutral-800">
                    {recentActivity.map((item) => item.destination ? (
                      <Link className="block p-4 hover:bg-neutral-900" href={item.destination} key={item.id}><span>{item.description}</span><time className="mt-1 block text-xs text-neutral-500">{new Date(item.created_at).toLocaleString()}</time></Link>
                    ) : (
                      <div className="p-4" key={item.id}><span>{item.description}</span><time className="mt-1 block text-xs text-neutral-500">{new Date(item.created_at).toLocaleString()}</time></div>
                    ))}
                    {!recentActivity.length && <p className="p-5 text-sm text-neutral-500">No recent activity.</p>}
                  </div>
                </section>
              </div>
            )}
            {!!data.upcoming_bookings.length && (
              <section className="mt-8">
                <div className="mb-4 flex items-center justify-between"><h2 className="font-semibold">Upcoming bookings</h2><Link className="text-sm text-neutral-400" href="/workspace/bookings">View all</Link></div>
                <div className="divide-y divide-neutral-800 rounded-md border border-neutral-800">
                  {data.upcoming_bookings.map((item) => (
                    <Link className="grid gap-2 p-4 hover:bg-neutral-900 sm:grid-cols-[1fr_auto_auto]" href={`/workspace/bookings/${item.id}`} key={item.id}>
                      <span><strong>{item.artist}</strong><span className="ml-2 text-xs text-neutral-500">{item.reference}</span></span>
                      <span className="text-sm text-neutral-400">{item.venue || "Venue TBC"}</span>
                      <span className="text-sm tabular-nums">{item.days_out === 0 ? "Today" : `${item.days_out} days`} / {item.status}</span>
                    </Link>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </AppShell>
    </RouteGuard>
  );
}

export function WorkspaceOverviewPage() {
  const { activeOrganizationId, session } = useAuth();
  const membership = session?.memberships.find(
    (item) => item.organization.id === activeOrganizationId,
  );
  const { data, error } = useResource<Organization>(
    activeOrganizationId ? `/api/organizations/${activeOrganizationId}/` : null,
  );
  return (
    <WorkspaceFrame>
      <PageHeader
        eyebrow="Workspace"
        title={data?.name ?? "Organization overview"}
        description="Current organization access, team, booking, and invitation status."
      />
      <Notice message={error} error />
      {data ? (
        <>
          <div className="mt-7 grid gap-4 sm:grid-cols-3">
            <StatCard label="Your role" value={session?.user.is_superuser ? "platform superuser" : membership?.role ?? "-"} />
            <StatCard
              label="Upcoming bookings"
              value={data.upcoming_booking_count}
            />
            <StatCard
              label="Confirmed bookings"
              value={data.confirmed_booking_count}
            />
          </div>
          <div className="mt-7 flex flex-wrap gap-3">
            {hasOrganizationPermission(session, activeOrganizationId, "booking.manage") && (
              <Link className={buttonClass} href="/workspace/bookings/new">
                Create booking
              </Link>
            )}
            {hasOrganizationPermission(session, activeOrganizationId, "artist.manage") && (
              <Link
                className={secondaryButtonClass}
                href="/workspace/artists/new"
              >
                Add artist
              </Link>
            )}
            {hasOrganizationPermission(session, activeOrganizationId, "promoter.manage") && (
              <Link
                className={secondaryButtonClass}
                href="/workspace/promoters/new"
              >
                Add promoter
              </Link>
            )}
            {hasOrganizationPermission(session, activeOrganizationId, "venue.manage") && (
              <Link
                className={secondaryButtonClass}
                href="/workspace/venues/new"
              >
                Add venue
              </Link>
            )}
          </div>
          <div className="mt-7 flex flex-wrap gap-3">
            <Link className={buttonClass} href="/workspace/team">
              Manage team
            </Link>
            <Link
              className={secondaryButtonClass}
              href="/workspace/invitations"
            >
              Invitations
            </Link>
            <Link
              className={secondaryButtonClass}
              href="/workspace/organization"
            >
              Organization settings
            </Link>
          </div>
        </>
      ) : (
        <Loading />
      )}
    </WorkspaceFrame>
  );
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
  const canManage = hasOrganizationPermission(session, activeOrganizationId, "membership.manage");
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
          {["owner", "admin", "manager", "member", "artist"].map((value) => (
            <option key={value}>{value}</option>
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
                        {["owner", "admin", "manager", "member", "artist"].map(
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
                      <button
                        className={secondaryButtonClass}
                        onClick={() =>
                          void update(item, { is_active: !item.is_active })
                        }
                      >
                        {item.is_active ? "Deactivate" : "Activate"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </WorkspaceFrame>
  );
}

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
      setEmail("");
      setMessage(
        "Invitation generated. Copy the token now; it will not be shown again.",
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
        description="Seven-day invitations. Email delivery is not configured."
      />
      {canManage && (
        <form
          className="mt-7 grid gap-3 rounded-md border border-neutral-800 bg-neutral-900 p-5 sm:grid-cols-[1fr_12rem_auto]"
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
            Role
            <select
              className={`mt-2 ${fieldClass}`}
              value={role}
              onChange={(e) => setRole(e.target.value)}
            >
              {["owner", "admin", "manager", "member", "artist"].map(
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
          <code className="mt-3 block break-all rounded-md border border-amber-800 bg-neutral-900 p-4 text-sm text-amber-300">
            {token}
          </code>
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
              className="grid gap-3 rounded-md border border-neutral-800 bg-neutral-900 p-4 sm:grid-cols-[1fr_auto_auto] sm:items-center"
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
            className="mt-4 grid gap-5 rounded-md border border-neutral-800 bg-neutral-900 p-6"
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
    memberships: Member[];
  }>("/api/profile/");
  const [message, setMessage] = useState("");
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const element = event.currentTarget; const form = new FormData(element);
    try {
      await apiRequest("/api/profile/", {
        method: "PATCH",
        body: JSON.stringify({
          first_name: form.get("first_name"),
          last_name: form.get("last_name"),
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
              key={`${data.first_name}-${data.last_name}`}
              className="grid gap-5 rounded-md border border-neutral-800 bg-neutral-900 p-6"
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
              <button className={buttonClass}>Save profile</button>
            </form>
          ) : (
            <Loading />
          )}
          <div className="rounded-md border border-neutral-800 bg-neutral-900 p-6">
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
              className="grid gap-2 rounded-md border border-neutral-800 bg-neutral-900 p-5 hover:border-neutral-600 sm:grid-cols-[1fr_auto_auto]"
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
              className="grid gap-2 rounded-md border border-neutral-800 bg-neutral-900 p-5 hover:border-neutral-600 sm:grid-cols-[1fr_auto_auto]"
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
              className="rounded-md border border-neutral-800 bg-neutral-900 p-4"
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
  const { session } = useAuth();
  const [message, setMessage] = useState("");
  async function accept() {
    try {
      const membership = await apiRequest<Member>("/api/invitations/accept/", {
        method: "POST",
        body: JSON.stringify({ token }),
      });
      setMessage(`Invitation accepted for ${membership.organization.name}.`);
    } catch (caught) {
      setMessage(
        caught instanceof Error
          ? caught.message
          : "Unable to accept invitation.",
      );
    }
  }
  return (
    <main className="grid min-h-screen place-items-center bg-neutral-950 p-5 text-neutral-100">
      <section className="w-full max-w-lg rounded-md border border-neutral-800 bg-neutral-900 p-7">
        <p className="text-xs font-semibold uppercase text-amber-400">
          Evolve invitation
        </p>
        <h1 className="mt-3 text-3xl font-semibold">Join organization</h1>
        <p className="mt-3 text-sm leading-6 text-neutral-400">
          Sign in with the invited email address, then accept this invitation.
        </p>
        <div className="mt-6">
          <Notice
            message={message}
            error={
              message.toLowerCase().includes("invalid") ||
              message.toLowerCase().includes("expired")
            }
          />
        </div>
        {session ? (
          <button
            className={`mt-6 ${buttonClass}`}
            onClick={() => void accept()}
          >
            Accept invitation
          </button>
        ) : (
          <Link
            className={`mt-6 ${buttonClass}`}
            href={`/login?next=/invite/${encodeURIComponent(token)}`}
          >
            Sign in to continue
          </Link>
        )}
      </section>
    </main>
  );
}
