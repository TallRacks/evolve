"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { RouteGuard } from "@/components/auth/route-guard";
import { useAuth } from "@/components/auth/auth-provider";
import { apiRequest } from "@/lib/api/client";
import { hasOrganizationPermission } from "@/lib/auth/access";
import { buttonClass, EmptyState, fieldClass, PageHeader, secondaryButtonClass } from "@/components/ui/page";

type SchemaState = { missing_columns: { key: string; header: string }[]; custom_columns: { key: string; header: string }[]; columns: string[] };
type Connector = { id: string; name: string; connection_status: string; is_active: boolean };
type Tracker = {
  id: string;
  name: string;
  kind: string;
  google_connector: string;
  spreadsheet_id: string;
  worksheet_name: string;
  direction: string;
  field_mapping: Record<string, string>;
  schema_state: SchemaState;
  last_sync_status: string;
  last_sync_message: string;
};
const panel = "evolve-panel p-5";

export function TrackerSyncStrip() {
  const { activeOrganizationId, session } = useAuth();
  const [items, setItems] = useState<Tracker[]>([]);
  const [message, setMessage] = useState("");
  const canView = hasOrganizationPermission(session, activeOrganizationId, "calendar.view");
  const canManage = hasOrganizationPermission(session, activeOrganizationId, "calendar.manage");
  useEffect(() => {
    if (!activeOrganizationId) return;
    let current = true;
    void apiRequest<Tracker[]>("/api/trackers/?organization_id=" + activeOrganizationId)
      .then((rows) => { if (current) setItems(rows); })
      .catch(() => { if (current) setItems([]); });
    return () => { current = false; };
  }, [activeOrganizationId]);
  async function load() {
    if (!activeOrganizationId) return;
    try { setItems(await apiRequest<Tracker[]>("/api/trackers/?organization_id=" + activeOrganizationId)); }
    catch { setItems([]); }
  }
  async function sync(item: Tracker, direction: "import" | "export") {
    if (!activeOrganizationId) return;
    try {
      await apiRequest("/api/trackers/" + item.id + "/sync/", { method: "POST", body: JSON.stringify({ organization_id: activeOrganizationId, direction }) });
      setMessage(item.name + ": " + direction + " queued.");
      await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to queue worksheet sync."); }
  }
  if (!activeOrganizationId || !canView) return null;
  return <section className="evolve-panel mt-6 flex flex-wrap items-center justify-between gap-3 p-4">
    <div>
      <p className="text-sm font-semibold">Connected worksheet trackers</p>
      <p className="mt-1 text-xs text-[var(--text-muted)]">Import shows and export updates through the connected Google Sheet.</p>
    </div>
    {items.length ? <div className="flex flex-wrap gap-2">{items.map((item) => <span className="flex items-center gap-2" key={item.id}><span className="text-xs text-[var(--text-muted)]">{item.name}</span><button className={secondaryButtonClass} disabled={!canManage} onClick={() => void sync(item, "import")}>Import</button><button className={buttonClass} disabled={!canManage} onClick={() => void sync(item, "export")}>Sync to sheet</button></span>)}</div> : <div className="flex flex-wrap items-center gap-2"><span className="text-xs text-[var(--text-muted)]">No tracker configured yet.</span><Link className={secondaryButtonClass} href="/workspace/settings/trackers">Configure tracker</Link></div>}
    {!canManage && items.length ? <p className="basis-full text-xs text-amber-700">Calendar management permission is required to run a sync.</p> : null}
    {message && <p className="basis-full text-xs text-[var(--accent-strong)]" role="status">{message}</p>}
  </section>;
}

export function TrackerPage() {
  const { activeOrganizationId, session } = useAuth();
  const [items, setItems] = useState<Tracker[]>([]);
  const [schema, setSchema] = useState<Record<string, SchemaState>>({});
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [message, setMessage] = useState("");
  const [connectorError, setConnectorError] = useState("");
  const [editing, setEditing] = useState<Tracker | null>(null);
  const [saving, setSaving] = useState(false);
  const canManage = hasOrganizationPermission(session, activeOrganizationId, "calendar.manage");
  const load = () => activeOrganizationId ? apiRequest<Tracker[]>(`/api/trackers/?organization_id=${activeOrganizationId}`).then(setItems) : Promise.resolve();
  useEffect(() => { if (!activeOrganizationId) return; void load(); void apiRequest<Connector[]>("/api/google-workspace/available/?organization_id=" + activeOrganizationId).then((rows) => { setConnectors(rows); setConnectorError(rows.length ? "" : "No active Google Sheets connector is available. Activate and test Google Workspace first."); }).catch((error) => { setConnectors([]); setConnectorError(error instanceof Error ? error.message : "Unable to load Google Sheets connectors."); }); }, [activeOrganizationId]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeOrganizationId) return;
    const data = Object.fromEntries(new FormData(event.currentTarget));
    const isEditing = Boolean(editing);
    setSaving(true);
    setMessage("");
    try {
      await apiRequest(isEditing ? `/api/trackers/${editing?.id}/` : "/api/trackers/", {
        method: isEditing ? "PATCH" : "POST",
        body: JSON.stringify({ ...data, organization_id: activeOrganizationId, ...(isEditing ? {} : { field_mapping: {} }) }),
      });
      event.currentTarget.reset();
      setEditing(null);
      setMessage(isEditing ? "Tracker updated." : "Tracker saved.");
      await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : isEditing ? "Unable to update tracker." : "Unable to save tracker."); }
    finally { setSaving(false); }
  }

  async function sync(item: Tracker, direction: "import" | "export") {
    try {
      const result = await apiRequest<{ message?: string }>(`/api/trackers/${item.id}/sync/`, { method: "POST", body: JSON.stringify({ organization_id: activeOrganizationId, direction }) });
      setMessage(result.message ?? `${direction} sync completed.`);
      await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to queue sync."); }
  }

  async function reconcile(item: Tracker) {
    try {
      const state = await apiRequest<SchemaState>(`/api/trackers/${item.id}/schema/`, { method: "POST", body: JSON.stringify({ organization_id: activeOrganizationId, apply_headers: true }) });
      setSchema((current) => ({ ...current, [item.id]: state }));
      setMessage(state.missing_columns.length ? `Added ${state.missing_columns.length} missing booking columns to the sheet.` : "Sheet headers are already aligned.");
      await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to reconcile sheet headers."); }
  }

  return <RouteGuard portal="workspace"><AppShell organizationScoped><main className="p-4 sm:p-8"><PageHeader eyebrow="Workspace data" title="Spreadsheet trackers" description="Connect a Google Sheet, validate its worksheet, and keep its columns aligned with Evolve." actions={<a className="evolve-tool-button" href="/platform/google-workspace">Configure Google Workspace</a>}/><div className="mt-6 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--background-soft)] p-4 text-sm"><p className="font-semibold">Booking sheet format</p><p className="mt-2 text-[var(--text-secondary)]">Required for a reliable import: <strong>Event Date</strong> and <strong>Artist</strong> (Artist may be omitted only when the organization has one active artist). Event Name, Promoter, Venue, Status, Event Type, Performance Type, and contact columns are then matched by their header names.</p><p className="mt-2 text-[var(--text-secondary)]"><strong>Date:</strong> YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, DD Month YYYY (for example 02 October 2026), DD Mon YYYY (02 Oct 2026), or an Excel date. <strong>Time:</strong> HH:MM (19:30), 12-hour (7:30 PM), or 19h30 in <strong>Performance Time</strong>; it is combined with Event Date. A full value may also be YYYY-MM-DD HH:MM or an ISO timestamp. Set <strong>Timezone</strong> to an IANA value such as Africa/Johannesburg.</p><p className="mt-2 text-xs text-[var(--text-muted)]">Keep one show per row, use Booking Reference for stable updates, and avoid merged cells. Reconcile headers after adding columns; imports preserve custom fields and update matching bookings instead of creating duplicates.</p></div><div className="mt-7 grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]"><section className="grid gap-3">{connectorError && <div className="evolve-panel border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">{connectorError} <a className="ml-1 font-semibold underline" href="/platform/google-workspace">Open Google Workspace settings</a></div>}{items.map((item) => { const state = schema[item.id] ?? item.schema_state; return <article className={panel} key={item.id}><div className="flex flex-wrap justify-between gap-3"><div><h2 className="font-semibold">{item.name}</h2><p className="mt-1 text-sm text-[var(--text-muted)]">{item.kind} · {item.worksheet_name} · {item.direction}</p><p className="mt-2 text-xs text-[var(--text-muted)]">{item.last_sync_status}: {item.last_sync_message || "No sync requested."}</p></div>{canManage && <div className="flex flex-wrap gap-2"><button className={secondaryButtonClass} onClick={() => setEditing(item)}>Edit</button><button className={secondaryButtonClass} onClick={() => void reconcile(item)}>Reconcile headers</button><button className={secondaryButtonClass} onClick={() => void sync(item, "import")}>Import</button><button className={secondaryButtonClass} onClick={() => void sync(item, "export")}>Export</button></div>}</div><p className="mt-3 text-xs text-[var(--text-muted)]">Spreadsheet: {item.spreadsheet_id}</p>{state?.columns?.length ? <div className="mt-4 grid gap-2 text-xs"><p><span className="font-medium">Columns:</span> {state.columns.join(" · ")}</p>{state.missing_columns?.length ? <p className="text-amber-700">Added or pending canonical columns: {state.missing_columns.map((column) => column.header).join(", ")}</p> : null}{state.custom_columns?.length ? <p className="text-[var(--text-muted)]">New sheet columns available for mapping: {state.custom_columns.map((column) => column.header).join(", ")}</p> : null}</div> : <p className="mt-4 text-xs text-[var(--text-muted)]">No schema has been reconciled yet.</p>}</article>; })}{!items.length && <EmptyState title="No trackers configured" detail="Add a Google Sheets tracker for each workspace data set."/>}</section>{canManage && <form key={editing?.id ?? "new"} className={`${panel} grid content-start gap-4`} onSubmit={save}><div className="flex items-center justify-between gap-3"><h2 className="font-semibold">{editing ? "Edit tracker" : "New tracker"}</h2>{editing && <button type="button" className="text-xs font-medium text-[var(--text-muted)] underline" onClick={() => setEditing(null)}>Cancel</button>}</div><input className={fieldClass} name="name" defaultValue={editing?.name ?? ""} placeholder="Bookings tracker" required/><select className={fieldClass} name="kind" defaultValue={editing?.kind ?? "bookings"}><option value="bookings">Bookings</option><option value="tasks">Tasks</option><option value="events">Events</option><option value="releases">Releases</option></select><select className={fieldClass} name="google_connector" required defaultValue={editing?.google_connector ?? ""}><option value="" disabled>Select Google Sheets connector</option>{connectors.map((connector) => <option key={connector.id} value={connector.id}>{connector.name} - {connector.connection_status}</option>)}</select><input className={fieldClass} name="spreadsheet_id" defaultValue={editing?.spreadsheet_id ?? ""} placeholder="Spreadsheet ID" required/><input className={fieldClass} name="worksheet_name" defaultValue={editing?.worksheet_name ?? "Sheet1"} placeholder="Worksheet name" required/><select className={fieldClass} name="direction" defaultValue={editing?.direction ?? "sheet_source"}><option value="sheet_source">Spreadsheet is source of truth</option><option value="evolve_source">Evolve is source of truth</option></select><p className="text-xs text-[var(--text-muted)]">Canonical booking headers are added to the sheet. Any extra sheet headers are retained as custom fields for later mapping.</p><button className={buttonClass} disabled={!connectors.length || saving}>{saving ? "Saving…" : editing ? "Save changes" : "Save tracker"}</button>{message && <p className="text-sm text-[var(--accent-strong)]" role="status">{message}</p>}</form>}</div>{message && <p className="mt-4 text-sm">{message}</p>}</main></AppShell></RouteGuard>;
}
