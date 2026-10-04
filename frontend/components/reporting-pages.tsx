"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { RouteGuard } from "@/components/auth/route-guard";
import { useAuth } from "@/components/auth/auth-provider";
import { confirmAction } from "@/components/ui/action-dialog";
import {
  buttonClass,
  EmptyState,
  fieldClass,
  PageHeader,
  secondaryButtonClass,
  StatCard,
} from "@/components/ui/page";
import { apiRequest } from "@/lib/api/client";

const REPORTS = [
  { key: "bookings", title: "Booking Pipeline", group: "Live", permission: "booking.view", description: "Pipeline, priority and readiness across current bookings." },
  { key: "production", title: "Production Attention", group: "Live", permission: "production.view", description: "Advances and show operations requiring attention." },
  { key: "travel", title: "Travel", group: "Live", permission: "travel.view", description: "Upcoming itineraries and confirmation state without private references." },
  { key: "tasks", title: "Tasks & Workload", group: "Live", permission: "task.view", description: "Operational workload by status, priority and assignee." },
  { key: "finance", title: "Finance", group: "Business", permission: "finance.view", description: "Invoice and payment state, strictly separated by currency." },
  { key: "contracts", title: "Contracts", group: "Business", permission: "contract.view", description: "Contract lifecycle and expiry attention." },
  { key: "music", title: "Releases", group: "Music & Marketing", permission: "music.view", description: "Release pipeline and identifier completeness." },
  { key: "campaigns", title: "Campaigns & Rollouts", group: "Music & Marketing", permission: "campaign.view", description: "Campaign status and delivery progress." },
  { key: "rights", title: "Rights Completeness", group: "Rights", permission: "rights.view", description: "Work, track and ownership completeness signals." },
  { key: "royalties", title: "Royalty Statements", group: "Rights", permission: "royalties.view", description: "Statement lifecycle and reconciliation state." },
  { key: "artists", title: "Artist Activity", group: "People & Artists", permission: "artist.view", description: "Operational activity by authorized Artist." },
  { key: "promoters", title: "Promoters", group: "People & Artists", permission: "promoter.view", description: "Most active relationships by Booking count." },
  { key: "venues", title: "Venues", group: "People & Artists", permission: "venue.view", description: "Booking and production activity by Venue." },
] as const;

interface ReportData {
  report_key: string;
  title: string;
  summary: {
    total: number;
    by_status?: Record<string, number>;
    currencies?: Record<string, unknown>;
  };
  rows: Record<string, unknown>[];
  pagination: { page: number; page_size: number; pages: number; total: number };
}
interface SavedView {
  id: string;
  report_key: string;
  name: string;
  filters: Record<string, string>;
  sort: string;
  is_default: boolean;
}
interface FilterState {
  status: string;
  priority: string;
  date_from: string;
  date_to: string;
  sort: string;
  page: number;
}
const EMPTY_FILTERS: FilterState = {
  status: "",
  priority: "",
  date_from: "",
  date_to: "",
  sort: "",
  page: 1,
};

function Frame({ children }: { children: React.ReactNode }) {
  return <RouteGuard portal="workspace"><AppShell organizationScoped>{children}</AppShell></RouteGuard>;
}

export function ReportsHubPage() {
  const { session, activeOrganizationId } = useAuth();
  const membership = session?.memberships.find((item) => item.organization.id === activeOrganizationId);
  const permissions = membership?.permissions ?? [];
  const can = (permission: string) => Boolean(session?.user.is_superuser || permissions.includes(permission));
  const visible = REPORTS.filter((report) => can("reporting.view") && can(report.permission));
  const groups = [...new Set(visible.map((report) => report.group))];
  return <Frame>
    <PageHeader eyebrow="Insights" title="Reports" description="Permission-aware operational reporting from current source records." />
    <div className="mt-7 space-y-8">
      {groups.map((group) => <section key={group}>
        <h2 className="text-xs font-semibold uppercase text-neutral-500">{group}</h2>
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {visible.filter((report) => report.group === group).map((report) => <Link className="evolve-panel p-5 hover:border-neutral-600" href={`/workspace/reports/${report.key}`} key={report.key}>
            <h3 className="font-semibold">{report.title}</h3>
            <p className="mt-2 text-sm text-neutral-400">{report.description}</p>
            <span className="mt-4 inline-block text-sm text-amber-300">Open report</span>
          </Link>)}
        </div>
      </section>)}
      {visible.length === 0 && <EmptyState title="No reports available" detail="Reports appear when both reporting and source-domain access are granted." />}
    </div>
  </Frame>;
}

export function ReportPage({ reportKey }: { reportKey: string }) {
  const router = useRouter();
  const { activeOrganizationId } = useAuth();
  const definition = REPORTS.find((item) => item.key === reportKey);
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [data, setData] = useState<ReportData | null>(null);
  const [saved, setSaved] = useState<SavedView[]>([]);
  const [message, setMessage] = useState("");
  const [saveOpen, setSaveOpen] = useState(false);
  const [editing, setEditing] = useState<SavedView | null>(null);
  const query = useMemo(() => {
    const params = new URLSearchParams({ organization_id: activeOrganizationId ?? "" });
    Object.entries(filters).forEach(([key, value]) => {
      if (value && !(key === "page" && value === 1)) params.set(key, String(value));
    });
    return params.toString();
  }, [activeOrganizationId, filters]);
  const loadSaved = useCallback(async () => {
    if (!activeOrganizationId) return;
    setSaved(await apiRequest<SavedView[]>(`/api/reports/saved-views/?organization_id=${activeOrganizationId}`));
  }, [activeOrganizationId]);
  useEffect(() => {
    if (!activeOrganizationId || !definition) return;
    let cancelled = false;
    apiRequest<ReportData>(`/api/reports/${reportKey}/?${query}`)
      .then((next) => { if (!cancelled) { setData(next); setMessage(""); } })
      .catch((error) => { if (!cancelled) { setData(null); setMessage(error instanceof Error ? error.message : "Unable to load report."); } });
    return () => { cancelled = true; };
  }, [activeOrganizationId, definition, query, reportKey]);
  useEffect(() => {
    if (!activeOrganizationId) return;
    let cancelled = false;
    apiRequest<SavedView[]>(`/api/reports/saved-views/?organization_id=${activeOrganizationId}`).then((next) => {
      if (!cancelled) setSaved(next);
    });
    return () => { cancelled = true; };
  }, [activeOrganizationId]);
  useEffect(() => {
    const visible = new URLSearchParams(query);
    visible.delete("organization_id");
    window.history.replaceState(null, "", `${window.location.pathname}${visible.size ? `?${visible}` : ""}`);
  }, [query]);
  if (!definition) return <Frame><EmptyState title="Report not found" detail="This report key is not registered." /></Frame>;
  function update(key: keyof FilterState, value: string | number) {
    setFilters((current) => ({ ...current, [key]: value, page: key === "page" ? Number(value) : 1 }));
  }
  async function saveView(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeOrganizationId) return;
    const form = new FormData(event.currentTarget);
    const body = {
      organization_id: activeOrganizationId,
      report_key: reportKey,
      name: form.get("name"),
      filters: Object.fromEntries(Object.entries({ status: filters.status, priority: filters.priority, date_from: filters.date_from, date_to: filters.date_to }).filter(([, value]) => value)),
      sort: filters.sort,
      is_default: form.get("is_default") === "on",
    };
    if (editing) await apiRequest(`/api/reports/saved-views/${editing.id}/`, { method: "PATCH", body: JSON.stringify(body) });
    else await apiRequest("/api/reports/saved-views/", { method: "POST", body: JSON.stringify(body) });
    setEditing(null); setSaveOpen(false); setMessage("Saved view updated."); await loadSaved();
  }
  function applyView(item: SavedView) {
    setFilters({ ...EMPTY_FILTERS, ...item.filters, sort: item.sort || "" });
  }
  async function setDefault(item: SavedView) {
    await apiRequest(`/api/reports/saved-views/${item.id}/`, { method: "PATCH", body: JSON.stringify({ is_default: true }) });
    await loadSaved();
  }
  async function removeView(item: SavedView) {
    if (!await confirmAction(`Delete saved view ${item.name}?`)) return;
    await apiRequest(`/api/reports/saved-views/${item.id}/`, { method: "DELETE" });
    await loadSaved();
  }
  return <Frame>
    <PageHeader eyebrow="Reports" title={definition.title} description={definition.description} actions={<div className="flex gap-2"><button className={secondaryButtonClass} onClick={() => { setEditing(null); setSaveOpen(true); }}>Save view</button><a className={buttonClass} href={`/api/reports/${reportKey}/export/?${query}`}>Export CSV</a></div>} />
    <button className="mt-4 text-sm text-neutral-400" onClick={() => router.push("/workspace/reports")}>Back to Reports</button>
    <section className="mt-5 grid gap-3 rounded-md border border-neutral-800 p-4 sm:grid-cols-2 lg:grid-cols-6" aria-label="Report filters">
      {reportKey !== "finance" && <label className="text-sm">Status<input className={`mt-1 ${fieldClass}`} value={filters.status} onChange={(event) => update("status", event.target.value)} placeholder="All" /></label>}
      {["bookings", "tasks"].includes(reportKey) && <label className="text-sm">Priority<input className={`mt-1 ${fieldClass}`} value={filters.priority} onChange={(event) => update("priority", event.target.value)} placeholder="All" /></label>}
      {["bookings", "production", "travel", "tasks", "contracts", "music", "campaigns", "royalties"].includes(reportKey) && <><label className="text-sm">From<input className={`mt-1 ${fieldClass}`} type="date" value={filters.date_from} onChange={(event) => update("date_from", event.target.value)} /></label>
      <label className="text-sm">To<input className={`mt-1 ${fieldClass}`} type="date" value={filters.date_to} onChange={(event) => update("date_to", event.target.value)} /></label></>}
      <label className="text-sm">Sort<select className={`mt-1 ${fieldClass}`} value={filters.sort} onChange={(event) => update("sort", event.target.value)}><option value="">Default</option><option value="status">Status</option><option value="-status">Status descending</option></select></label>
      <button className={`self-end ${secondaryButtonClass}`} onClick={() => setFilters(EMPTY_FILTERS)}>Reset filters</button>
    </section>
    {message && <p aria-live="polite" className="mt-4 text-sm text-amber-300">{message}</p>}
    {data && <>
      <div className="mt-6 grid gap-3 sm:grid-cols-3"><StatCard label="Records" value={data.summary.total} />{Object.entries(data.summary.by_status ?? {}).slice(0, 2).map(([key, value]) => <StatCard label={key.replaceAll("_", " ")} value={value} key={key} />)}</div>
      {data.summary.currencies && <div className="mt-5 overflow-x-auto evolve-panel p-4"><pre className="text-xs">{JSON.stringify(data.summary.currencies, null, 2)}</pre></div>}
      <div className="mt-6 overflow-x-auto rounded-md border border-neutral-800">{data.rows.length === 0 ? <EmptyState title="No report rows" detail="No records match these filters." /> : <table className="min-w-full text-left text-sm"><thead className="bg-neutral-900"><tr>{Object.keys(data.rows[0]).map((key) => <th className="px-4 py-3" key={key}>{key.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{data.rows.map((row, index) => <tr className="border-t border-neutral-800" key={index}>{Object.values(row).map((value, cell) => <td className="whitespace-nowrap px-4 py-3" key={cell}>{String(value)}</td>)}</tr>)}</tbody></table>}</div>
      <div className="mt-4 flex items-center justify-between text-sm"><span>Page {data.pagination.page} of {data.pagination.pages}</span><div className="flex gap-2"><button className={secondaryButtonClass} disabled={filters.page <= 1} onClick={() => update("page", filters.page - 1)}>Previous</button><button className={secondaryButtonClass} disabled={filters.page >= data.pagination.pages} onClick={() => update("page", filters.page + 1)}>Next</button></div></div>
    </>}
    <section className="mt-8 border-t border-neutral-800 pt-6"><div className="flex items-center justify-between"><h2 className="font-semibold">Saved views</h2><button className={secondaryButtonClass} onClick={() => { setEditing(null); setSaveOpen(true); }}>Save current view</button></div><div className="mt-3 grid gap-2">{saved.filter((item) => item.report_key === reportKey).map((item) => <div className="flex flex-wrap items-center justify-between gap-3 border-t border-neutral-800 pt-3" key={item.id}><button className="text-left" onClick={() => applyView(item)}>{item.name}{item.is_default && <span className="ml-2 text-neutral-500">Default</span>}</button><div className="flex gap-2"><button className={secondaryButtonClass} onClick={() => { setEditing(item); setSaveOpen(true); }}>Rename / update</button>{!item.is_default && <button className={secondaryButtonClass} onClick={() => void setDefault(item)}>Set default</button>}<button className={secondaryButtonClass} onClick={() => void removeView(item)}>Delete</button></div></div>)}{saved.filter((item) => item.report_key === reportKey).length === 0 && <p className="text-sm text-neutral-500">No saved views.</p>}</div></section>
    {saveOpen && <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4" role="dialog" aria-modal="true" aria-labelledby="save-view-title"><form className="w-full max-w-md rounded-md border border-neutral-700 bg-neutral-950 p-5" onSubmit={saveView}><h2 className="font-semibold" id="save-view-title">{editing ? "Update saved view" : "Save current view"}</h2><label className="mt-4 block text-sm">Name<input autoFocus required name="name" className={`mt-1 ${fieldClass}`} defaultValue={editing?.name} /></label><label className="mt-4 flex items-center gap-2 text-sm"><input type="checkbox" name="is_default" defaultChecked={editing?.is_default} />Set as default</label><div className="mt-5 flex justify-end gap-2"><button type="button" className={secondaryButtonClass} onClick={() => { setEditing(null); setSaveOpen(false); }}>Cancel</button><button className={buttonClass}>Save</button></div></form></div>}
  </Frame>;
}
