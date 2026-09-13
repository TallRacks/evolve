"use client";

import { hasOrganizationPermission } from "@/lib/auth/access";
import { CalendarDays, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth/auth-provider";
import { RouteGuard } from "@/components/auth/route-guard";
import {
  buttonClass,
  EmptyState,
  fieldClass,
  PageHeader,
  secondaryButtonClass,
  StatusBadge,
} from "@/components/ui/page";
import { EntityDocumentsSection } from "@/components/calendar-document-pages";
import { BookingContractsSection } from "@/components/contract-pages";
import { BookingFinanceSection } from "@/components/finance-pages";
import { BookingTravelSection } from "@/components/travel-pages";
import { BookingProductionSection } from "@/components/production-pages";
import { apiRequest } from "@/lib/api/client";
import { confirmAction } from "@/components/ui/action-dialog";
import { OfficeGeneratorActions } from "@/components/office-generator-actions";

type Named = { id: string; name?: string; stage_name?: string };
type Organization = { id: string; name: string };
type Assignment = { id: string; responsibility: string; is_primary: boolean; is_active: boolean; member?: { membership_id: string; name: string; email: string }; contact_id?: string; snapshot_name?: string; snapshot_email?: string; snapshot_phone?: string };
type Activity = { id: string; action: string; description: string; actor: string | null; created_at: string };
type History = { id: string; from_status: string; to_status: string; changed_by: string | null; reason: string; created_at: string };
type Readiness = Record<string, { status: string; href: string }>;
type Booking = { id: string; reference: string; organization: Organization; title: string; artist: { id: string; stage_name: string }; promoter: Named | null; venue: Named | null; status: string; priority: string; event_date: string; event_start_datetime: string | null; event_end_datetime: string | null; timezone: string; promoter_name_snapshot: string; venue_name_snapshot: string; city_snapshot: string; country_snapshot: string; internal_notes?: string; currency?: string; performance_fee?: string | null; deposit_amount?: string | null; deposit_due_date?: string | null; balance_due_date?: string | null; allowed_transitions?: string[]; team?: Assignment[]; contacts?: Assignment[]; status_history?: History[]; activity?: Activity[]; days_out: number; readiness: Readiness; next_action?: { key: string; label: string; href: string } };
type Member = { id: string; user: { email: string; first_name: string; last_name: string }; is_active: boolean };
type Contact = { id: string; first_name: string; last_name: string; email: string; is_active: boolean };

const statuses = ["enquiry", "hold", "pending", "confirmed", "completed", "cancelled", "declined"];
const priorities = ["low", "normal", "high", "urgent"];
const priorityRank: Record<string, number> = { urgent: 0, high: 1, normal: 2, low: 3 };
const textareaClass = "min-h-28 w-full rounded-md border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm outline-none focus:border-amber-400";

function Frame({ platform, children }: { platform: boolean; children: React.ReactNode }) {
  return <RouteGuard portal={platform ? "platform" : "workspace"}><AppShell organizationScoped={!platform}>{children}</AppShell></RouteGuard>;
}

function Notice({ children, error = false }: { children: string; error?: boolean }) {
  return children ? <p className={`mt-4 rounded-md border p-3 text-sm ${error ? "border-red-900 text-red-200" : "border-emerald-900 text-emerald-200"}`}>{children}</p> : null;
}

export function BookingDirectory({ platform = false }: { platform?: boolean }) {
  const { activeOrganizationId, session } = useAuth();
  const [items, setItems] = useState<Booking[] | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [eventDate, setEventDate] = useState("");
  const canManage = platform || hasOrganizationPermission(session, activeOrganizationId, "booking.manage");
  useEffect(() => {
    const path = platform
      ? "/api/platform/bookings/"
      : activeOrganizationId
        ? `/api/bookings/?organization_id=${activeOrganizationId}`
        : null;
    if (!path) return;
    let current = true;
    apiRequest<Booking[]>(path)
      .then((next) => current && setItems(next))
      .catch((caught) => current && setError(caught instanceof Error ? caught.message : "Unable to load bookings."));
    return () => { current = false; };
  }, [activeOrganizationId, platform]);
  const filtered = useMemo(
    () => (items ?? []).filter((item) =>
      (!query || `${item.reference} ${item.title} ${item.artist.stage_name} ${item.promoter_name_snapshot} ${item.venue_name_snapshot}`.toLowerCase().includes(query.toLowerCase())) &&
      (!status || item.status === status) && (!priority || item.priority === priority) &&
      (!eventDate || item.event_date === eventDate)),
    [eventDate, items, priority, query, status],
  );
  const queue = useMemo(
    () => filtered
      .filter((item) => item.days_out >= 0 && item.days_out <= 30 &&
        (item.priority === "urgent" || item.priority === "high" ||
          Object.values(item.readiness).some((entry) => entry.status === "missing" || entry.status === "blocked")))
      .sort((a, b) => priorityRank[a.priority] - priorityRank[b.priority] || a.days_out - b.days_out)
      .slice(0, 8),
    [filtered],
  );
  const months = useMemo(() => {
    const grouped = new Map<string, Booking[]>();
    filtered
      .slice()
      .sort((a, b) => a.event_date.localeCompare(b.event_date))
      .forEach((item) => {
        const key = item.event_date.slice(0, 7);
        grouped.set(key, [...(grouped.get(key) ?? []), item]);
      });
    return [...grouped.entries()];
  }, [filtered]);
  const destination = (item: Booking) => `${platform ? "/platform" : "/workspace"}/bookings/${item.id}`;
  const daysLabel = (days: number) => days < 0 ? "Past" : days === 0 ? "Today" : days === 1 ? "1 day" : `${days} days`;
  return (
    <Frame platform={platform}>
      <PageHeader
        eyebrow={platform ? "Platform" : "Live operations"}
        title="Bookings"
        description="Priority actions, operational readiness, and the forward event calendar."
        actions={canManage && !platform ? <Link className={buttonClass} href="/workspace/bookings/new">Create booking</Link> : undefined}
      />
      <div className="mt-6 grid gap-3 md:grid-cols-4">
        <input className={fieldClass} placeholder="Search reference, artist, or venue" value={query} onChange={(event) => setQuery(event.target.value)} />
        <select className={fieldClass} value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All statuses</option>{statuses.map((value) => <option key={value}>{value}</option>)}</select>
        <select className={fieldClass} value={priority} onChange={(event) => setPriority(event.target.value)}><option value="">All priorities</option>{priorities.map((value) => <option key={value}>{value}</option>)}</select>
        <input className={fieldClass} type="date" aria-label="Event date" value={eventDate} onChange={(event) => setEventDate(event.target.value)} />
      </div>
      <Notice error>{error}</Notice>
      {items === null ? (
        <div aria-label="Loading bookings" className="mt-7 grid animate-pulse gap-3">
          <div className="h-24 rounded-md bg-neutral-900" />
          {[1, 2, 3].map((item) => <div className="h-16 rounded-md bg-neutral-900" key={item} />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="mt-7"><EmptyState title="No bookings" detail={canManage ? "Create the first booking for this organization." : "No bookings match these filters."} /></div>
      ) : (
        <>
          <section className="mt-8">
            <div className="mb-4 flex items-end justify-between gap-3">
              <div><p className="text-xs font-semibold uppercase text-amber-300">Priority queue</p><h2 className="mt-1 text-lg font-semibold">Action required</h2></div>
              <span className="text-sm text-neutral-500">Next 30 days</span>
            </div>
            {queue.length ? <div className="divide-y divide-neutral-800 rounded-md border border-neutral-800 bg-neutral-950">
              {queue.map((item) => {
                const missing = Object.entries(item.readiness).filter(([, entry]) => entry.status === "missing" || entry.status === "blocked");
                return <Link className="grid gap-3 p-4 hover:bg-neutral-900 md:grid-cols-[5rem_minmax(12rem,1.2fr)_minmax(10rem,1fr)_6rem_auto] md:items-center" href={destination(item)} key={item.id}>
                  <span className={`text-xs font-bold uppercase ${item.priority === "urgent" ? "text-red-300" : item.priority === "high" ? "text-amber-300" : "text-neutral-400"}`}>P{priorityRank[item.priority] + 1} {item.priority}</span>
                  <span className="min-w-0"><span className="block truncate font-medium">{item.artist.stage_name} / {item.title}</span><span className="block text-xs text-neutral-500">{item.reference} / {item.promoter_name_snapshot || "Promoter TBC"}</span></span>
                  <span className="text-sm text-neutral-400">{item.venue_name_snapshot || "Venue TBC"}{item.city_snapshot ? `, ${item.city_snapshot}` : ""}</span>
                  <span className="text-sm font-semibold tabular-nums">{daysLabel(item.days_out)}</span>
                  <span className="flex items-center justify-between gap-2 text-xs text-neutral-400">{missing.length ? `${missing.map(([key]) => key.replace("_", " ")).join(", ")} needed` : item.status}<ChevronRight size={16} /></span>
                </Link>;
              })}
            </div> : <div className="rounded-md border border-neutral-800 p-6 text-sm text-neutral-500">No upcoming booking requires priority action.</div>}
          </section>
          <section className="mt-8">
            <div className="mb-4 flex items-center gap-2"><CalendarDays size={18} className="text-neutral-400" /><h2 className="font-semibold">Booking calendar</h2></div>
            <div className="grid gap-3">
              {months.map(([month, bookings], monthIndex) => (
                <details className="overflow-hidden rounded-md border border-neutral-800" key={month} open={monthIndex === 0}>
                  <summary className="cursor-pointer bg-neutral-900 px-4 py-3 font-semibold">
                    {new Date(`${month}-01T00:00:00`).toLocaleDateString(undefined, { month: "long", year: "numeric" })}
                    <span className="ml-2 text-sm font-normal text-neutral-500">{bookings.length}</span>
                  </summary>
                  <div className="divide-y divide-neutral-800">
                    {bookings.map((item) => <div className="grid gap-3 p-4 md:grid-cols-[6rem_minmax(12rem,1fr)_minmax(10rem,1fr)_auto] md:items-center" key={item.id}>
                      <span className="text-sm tabular-nums"><strong>{new Date(`${item.event_date}T00:00:00`).toLocaleDateString(undefined, { day: "2-digit", month: "short" })}</strong><span className="block text-xs text-neutral-500">{daysLabel(item.days_out)}</span></span>
                      <Link className="min-w-0 hover:text-amber-300" href={destination(item)}><span className="block truncate font-medium">{item.artist.stage_name} / {item.title}</span><span className="block text-xs text-neutral-500">{item.reference}</span></Link>
                      <span className="text-sm text-neutral-400">{item.venue_name_snapshot || "Venue TBC"} / {item.promoter_name_snapshot || "Promoter TBC"}</span>
                      <div className="flex flex-wrap gap-1.5">{Object.entries(item.readiness).map(([key, entry]) => <Link className={`rounded border px-2 py-1 text-[11px] uppercase ${entry.status === "missing" || entry.status === "blocked" ? "border-amber-800 text-amber-200" : "border-neutral-700 text-neutral-400"}`} href={entry.href} key={key}>{key.replace("_", " ")}: {entry.status}</Link>)}</div>
                    </div>)}
                  </div>
                </details>
              ))}
            </div>
          </section>
        </>
      )}
    </Frame>
  );
}

export function BookingCreatePage() {
  const router = useRouter(); const { activeOrganizationId, session } = useAuth();
  const [artists, setArtists] = useState<Named[]>([]); const [promoters, setPromoters] = useState<Named[]>([]); const [venues, setVenues] = useState<Named[]>([]); const [contacts, setContacts] = useState<Contact[]>([]); const [members, setMembers] = useState<Member[]>([]); const [error, setError] = useState("");
  const commercial = hasOrganizationPermission(session, activeOrganizationId, "booking.commercial.manage");
  useEffect(() => { if (!activeOrganizationId) return; const suffix = `?organization_id=${activeOrganizationId}`; void Promise.all([apiRequest<Named[]>(`/api/artists/${suffix}`), apiRequest<Named[]>(`/api/promoters/${suffix}`), apiRequest<Named[]>(`/api/venues/${suffix}`), apiRequest<Contact[]>(`/api/contacts/${suffix}`), apiRequest<Member[]>(`/api/organizations/${activeOrganizationId}/members/`)]).then(([a, p, v, c, m]) => { setArtists(a); setPromoters(p); setVenues(v); setContacts(c); setMembers(m.filter((item) => item.is_active)); }).catch((caught) => setError(caught instanceof Error ? caught.message : "Unable to load booking options.")); }, [activeOrganizationId]);
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (!activeOrganizationId) return; const element = event.currentTarget; const form = new FormData(element); const value = (name: string) => form.get(name) || null; const payload = { organization_id: activeOrganizationId, title: value("title"), artist_id: value("artist_id"), promoter_id: value("promoter_id"), venue_id: value("venue_id"), event_date: value("event_date"), event_start_datetime: value("event_start_datetime"), event_end_datetime: value("event_end_datetime"), timezone: value("timezone"), priority: value("priority"), status: value("status"), internal_notes: form.get("internal_notes") ?? "", prepare_production: form.get("prepare_production") === "on", prepare_call_sheet: form.get("prepare_call_sheet") === "on", prepare_travel: form.get("prepare_travel") === "on", initial_membership_id: value("membership_id"), initial_contact_id: value("contact_id"), ...(commercial ? { currency: value("currency"), performance_fee: value("performance_fee"), deposit_amount: value("deposit_amount"), deposit_due_date: value("deposit_due_date"), balance_due_date: value("balance_due_date") } : {}) }; try { const booking = await apiRequest<Booking>("/api/bookings/", { method: "POST", body: JSON.stringify(payload) }); router.push("/workspace/bookings/"+booking.id+"?created=1"); } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to create booking."); } }
  return <Frame platform={false}><PageHeader eyebrow="Workspace" title="Create booking" description="Capture event identity, master-record links, scheduling, and initial ownership."/><Notice error>{error}</Notice><form className="mt-7 grid gap-7" onSubmit={submit}><Section title="Event"><Fields><Label text="Title"><input className={fieldClass} name="title" required/></Label><Label text="Artist"><select className={fieldClass} name="artist_id" required><option value="">Select artist</option>{artists.map((item) => <option key={item.id} value={item.id}>{item.stage_name}</option>)}</select></Label><Label text="Event date"><input className={fieldClass} name="event_date" type="date" required/></Label><Label text="Timezone"><input className={fieldClass} name="timezone" defaultValue="Africa/Johannesburg" required/></Label><Label text="Starts"><input className={fieldClass} name="event_start_datetime" type="datetime-local"/></Label><Label text="Ends"><input className={fieldClass} name="event_end_datetime" type="datetime-local"/></Label></Fields></Section><Section title="Partners and ownership"><Fields><Label text="Promoter"><select className={fieldClass} name="promoter_id"><option value="">Not selected</option>{promoters.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Label><Label text="Venue"><select className={fieldClass} name="venue_id"><option value="">TBC</option>{venues.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Label><Label text="Primary team member"><select className={fieldClass} name="membership_id"><option value="">Not assigned</option>{members.map((item) => <option key={item.id} value={item.id}>{[item.user.first_name, item.user.last_name].filter(Boolean).join(" ") || item.user.email}</option>)}</select></Label><Label text="Primary booking contact"><select className={fieldClass} name="contact_id"><option value="">Not assigned</option>{contacts.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.first_name} {item.last_name}</option>)}</select></Label><Label text="Status"><select className={fieldClass} name="status" defaultValue="enquiry">{statuses.slice(0, 3).map((value) => <option key={value}>{value}</option>)}</select></Label><Label text="Priority"><select className={fieldClass} name="priority" defaultValue="normal">{priorities.map((value) => <option key={value}>{value}</option>)}</select></Label></Fields></Section>{commercial && <Section title="Commercial terms"><Fields><Label text="Currency"><input className={fieldClass} name="currency" defaultValue="ZAR" maxLength={3}/></Label><Label text="Performance fee"><input className={fieldClass} name="performance_fee" type="number" min="0" step="0.01"/></Label><Label text="Deposit"><input className={fieldClass} name="deposit_amount" type="number" min="0" step="0.01"/></Label><Label text="Deposit due"><input className={fieldClass} name="deposit_due_date" type="date"/></Label><Label text="Balance due"><input className={fieldClass} name="balance_due_date" type="date"/></Label></Fields></Section>}<Section title="Prepare operations"><div className="grid gap-3 sm:grid-cols-3"><label className="flex items-center gap-2"><input defaultChecked name="prepare_production" type="checkbox"/> Production Advance</label><label className="flex items-center gap-2"><input defaultChecked name="prepare_call_sheet" type="checkbox"/> Draft Call Sheet</label><label className="flex items-center gap-2"><input name="prepare_travel" type="checkbox"/> Travel Itinerary</label></div><p className="mt-3 text-sm text-neutral-500">These records are prepopulated from the Booking and can be changed later.</p></Section><Section title="Internal notes"><textarea className={textareaClass} name="internal_notes"/></Section><div><button className={buttonClass}>Create booking</button></div></form></Frame>;
}

function Fields({ children }: { children: React.ReactNode }) { return <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{children}</div>; }
function Label({ text, children }: { text: string; children: React.ReactNode }) { return <label className="grid gap-2 text-sm text-neutral-400">{text}{children}</label>; }
function Section({ title, children }: { title: string; children: React.ReactNode }) { return <section className="rounded-md border border-neutral-800 p-5"><h2 className="mb-5 font-semibold">{title}</h2>{children}</section>; }

export function BookingDetailPage({ id, platform = false }: { id: string; platform?: boolean }) {
  const { activeOrganizationId, session } = useAuth(); const [data, setData] = useState<Booking | null>(null); const [members, setMembers] = useState<Member[]>([]); const [contacts, setContacts] = useState<Contact[]>([]); const [message, setMessage] = useState(""); const [error, setError] = useState("");
  useEffect(() => { const notice = window.setTimeout(() => { if (new URLSearchParams(window.location.search).get("created") === "1") setMessage("Booking created and selected operational records prepared."); }, 0); return () => window.clearTimeout(notice); }, []);
  const canManage = platform || hasOrganizationPermission(session, activeOrganizationId, "booking.manage"); const canOffice = !platform && hasOrganizationPermission(session, activeOrganizationId, "booking.view") && hasOrganizationPermission(session, activeOrganizationId, "document.manage"); const canTeam = platform || hasOrganizationPermission(session, activeOrganizationId, "booking.team.manage");
  const path = platform ? `/api/platform/bookings/${id}/` : `/api/bookings/${id}/`; const load = useCallback(() => apiRequest<Booking>(path).then(setData).catch((caught) => setError(caught instanceof Error ? caught.message : "Unable to load booking.")), [path]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { const organizationId = platform ? data?.organization.id : activeOrganizationId; if (!organizationId || !canManage) return; const suffix = `?organization_id=${organizationId}`; void Promise.all([apiRequest<Member[]>(`/api/organizations/${organizationId}/members/`), apiRequest<Contact[]>(`/api/contacts/${suffix}`)]).then(([m, c]) => { setMembers(m.filter((item) => item.is_active)); setContacts(c.filter((item) => item.is_active)); }); }, [activeOrganizationId, canManage, data?.organization.id, platform]);
  async function save(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const element = event.currentTarget; const form = new FormData(element); const nullable = (name: string) => form.get(name) || null; const payload: Record<string, FormDataEntryValue | null> = { title: nullable("title"), priority: nullable("priority"), event_date: nullable("event_date"), event_start_datetime: nullable("event_start_datetime"), event_end_datetime: nullable("event_end_datetime"), timezone: nullable("timezone"), internal_notes: form.get("internal_notes") ?? "" }; if (data?.currency !== undefined) Object.assign(payload, { currency: nullable("currency"), performance_fee: nullable("performance_fee"), deposit_amount: nullable("deposit_amount"), deposit_due_date: nullable("deposit_due_date"), balance_due_date: nullable("balance_due_date") }); try { await apiRequest(path, { method: "PATCH", body: JSON.stringify(payload) }); setMessage("Booking updated."); await load(); } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to update booking."); } }
  async function transition(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const element = event.currentTarget; const form = new FormData(element); const toStatus = String(form.get("to_status")); if (!await confirmAction(`Change booking status to ${toStatus}?`)) return; try { await apiRequest(`/api/bookings/${id}/status/`, { method: "POST", body: JSON.stringify({ to_status: toStatus, reason: form.get("reason") }) }); setMessage("Status updated."); await load(); } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to change status."); } }
  async function addTeam(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const element = event.currentTarget; const form = new FormData(element); await apiRequest(`/api/bookings/${id}/team/`, { method: "POST", body: JSON.stringify({ membership_id: form.get("membership_id"), responsibility: form.get("responsibility"), is_primary: form.get("is_primary") === "on" }) }); element.reset(); await load(); }
  async function addContact(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const element = event.currentTarget; const form = new FormData(element); await apiRequest(`/api/bookings/${id}/contacts/`, { method: "POST", body: JSON.stringify({ contact_id: form.get("contact_id"), responsibility: form.get("responsibility"), is_primary: form.get("is_primary") === "on" }) }); element.reset(); await load(); }
  async function removeAssignment(kind: "team" | "contacts", assignment: Assignment) { if (!await confirmAction(`Remove this Booking ${kind === "team" ? "team assignment" : "contact relationship"}?`)) return; try { await apiRequest(`/api/bookings/${id}/${kind}/${assignment.id}/`, { method: "PATCH", body: JSON.stringify({ is_active: false, is_primary: false }) }); setMessage("Relationship removed."); await load(); } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to remove relationship."); } }
  return <Frame platform={platform}><PageHeader eyebrow={platform ? "Platform booking" : "Workspace booking"} title={data?.title ?? "Booking"} description={data ? `${data.reference} / ${data.artist.stage_name} / ${data.event_date}` : undefined} actions={data && canManage && !platform ? <div className="flex flex-wrap gap-2"><a className={secondaryButtonClass} href="#booking-edit">Edit Booking</a><Link className={buttonClass} href={`/workspace/bookings/${data.id}/call-sheet`}>Generate Call Sheet</Link></div> : undefined}/><Notice error>{error}</Notice><Notice>{message}</Notice>{!data ? <p className="py-12 text-neutral-500">Loading booking...</p> : <div className="mt-7 grid gap-7">{canOffice && <OfficeGeneratorActions source="booking" id={data.id} canManage={canOffice} />}<div className="flex flex-wrap items-center gap-3"><StatusBadge positive={data.status === "confirmed"}>{data.status}</StatusBadge><StatusBadge>{data.priority}</StatusBadge><span className="text-sm text-neutral-400">{data.venue_name_snapshot || "Venue TBC"}{data.city_snapshot ? `, ${data.city_snapshot}` : ""}</span><span className="text-sm text-neutral-500">{data.days_out >= 0 ? `${data.days_out} days out` : `${Math.abs(data.days_out)} days ago`}</span></div>{data.next_action && <section className="rounded-xl border border-amber-800 bg-amber-950/30 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-amber-300">Next best action</p><div className="mt-2 flex flex-wrap items-center justify-between gap-3"><p>{data.next_action.label}</p><Link className={buttonClass} href={data.next_action.href}>Open</Link></div></section>}<section aria-label="Operational readiness" className="grid gap-px overflow-hidden rounded-md border border-neutral-800 bg-neutral-800 sm:grid-cols-3 lg:grid-cols-5">{Object.entries(data.readiness).map(([key,entry])=><Link className="bg-neutral-950 p-4 hover:bg-neutral-900" href={entry.href} key={key}><span className="block text-xs font-semibold uppercase text-neutral-500">{key.replace("_"," ")}</span><span className={entry.status === "missing" || entry.status === "blocked" ? "mt-2 block text-sm text-amber-300" : "mt-2 block text-sm text-emerald-300"}>{entry.status.replaceAll("_"," ")}</span></Link>)}</section>{canManage && <form id="booking-edit" key={data.reference + data.status + data.event_date} className="grid gap-5" onSubmit={save}><Section title="Event details"><Fields><Label text="Title"><input className={fieldClass} name="title" defaultValue={data.title}/></Label><Label text="Event date"><input className={fieldClass} name="event_date" type="date" defaultValue={data.event_date}/></Label><Label text="Priority"><select className={fieldClass} name="priority" defaultValue={data.priority}>{priorities.map((value) => <option key={value}>{value}</option>)}</select></Label><Label text="Starts"><input className={fieldClass} name="event_start_datetime" type="datetime-local" defaultValue={data.event_start_datetime?.slice(0, 16)}/></Label><Label text="Ends"><input className={fieldClass} name="event_end_datetime" type="datetime-local" defaultValue={data.event_end_datetime?.slice(0, 16)}/></Label><Label text="Timezone"><input className={fieldClass} name="timezone" defaultValue={data.timezone}/></Label></Fields></Section>{data.currency !== undefined && <Section title="Commercial terms"><Fields><Label text="Currency"><input className={fieldClass} name="currency" defaultValue={data.currency}/></Label><Label text="Performance fee"><input className={fieldClass} name="performance_fee" type="number" step="0.01" defaultValue={data.performance_fee ?? ""}/></Label><Label text="Deposit"><input className={fieldClass} name="deposit_amount" type="number" step="0.01" defaultValue={data.deposit_amount ?? ""}/></Label><Label text="Deposit due"><input className={fieldClass} name="deposit_due_date" type="date" defaultValue={data.deposit_due_date ?? ""}/></Label><Label text="Balance due"><input className={fieldClass} name="balance_due_date" type="date" defaultValue={data.balance_due_date ?? ""}/></Label></Fields></Section>}<Section title="Internal notes"><textarea className={textareaClass} name="internal_notes" defaultValue={data.internal_notes}/></Section><div><button className={buttonClass}>Save changes</button></div></form>}{data.allowed_transitions && data.allowed_transitions.length > 0 && <Section title="Status transition"><form className="grid gap-3 sm:grid-cols-[12rem_1fr_auto]" onSubmit={transition}><select className={fieldClass} name="to_status">{data.allowed_transitions.map((value) => <option key={value}>{value}</option>)}</select><input className={fieldClass} name="reason" placeholder="Reason or context"/><button className={buttonClass}>Change status</button></form></Section>}<Section title="Team assignments">{data.team?.map((item) => <div className="flex justify-between border-t border-neutral-800 py-3 text-sm" key={item.id}><span>{item.member?.name}</span><span className="flex items-center gap-3 text-neutral-500">{item.responsibility}{item.is_primary ? " / primary" : ""}{canTeam&&<button className="text-red-300" onClick={()=>void removeAssignment("team",item)}>Remove</button>}</span></div>)}{canTeam && <form className="mt-4 grid gap-3 sm:grid-cols-[1fr_12rem_auto_auto]" onSubmit={addTeam}><select className={fieldClass} name="membership_id" required><option value="">Team member</option>{members.map((item) => <option key={item.id} value={item.id}>{[item.user.first_name, item.user.last_name].filter(Boolean).join(" ") || item.user.email}</option>)}</select><select className={fieldClass} name="responsibility">{["manager", "booking", "production", "finance", "marketing", "general"].map((value) => <option key={value}>{value}</option>)}</select><label className="flex items-center gap-2 text-sm"><input name="is_primary" type="checkbox"/> Primary</label><button className={secondaryButtonClass}>Assign</button></form>}</Section><Section title="Booking contacts">{data.contacts?.map((item) => <div className="flex justify-between border-t border-neutral-800 py-3 text-sm" key={item.id}><span>{item.snapshot_name}<span className="ml-2 text-neutral-500">{item.snapshot_email}</span></span><span className="flex items-center gap-3 text-neutral-500">{item.responsibility}{item.is_primary ? " / primary" : ""}{canManage&&<button className="text-red-300" onClick={()=>void removeAssignment("contacts",item)}>Remove</button>}</span></div>)}{canManage && <form className="mt-4 grid gap-3 sm:grid-cols-[1fr_12rem_auto_auto]" onSubmit={addContact}><select className={fieldClass} name="contact_id" required><option value="">Contact</option>{contacts.map((item) => <option key={item.id} value={item.id}>{item.first_name} {item.last_name}</option>)}</select><select className={fieldClass} name="responsibility">{["booking", "promoter", "venue", "production", "finance", "hospitality", "general"].map((value) => <option key={value}>{value}</option>)}</select><label className="flex items-center gap-2 text-sm"><input name="is_primary" type="checkbox"/> Primary</label><button className={secondaryButtonClass}>Add</button></form>}</Section><Section title="Status history">{data.status_history?.length ? data.status_history.map((item) => <div className="border-t border-neutral-800 py-3 text-sm" key={item.id}><p>{item.from_status} to {item.to_status}</p><p className="text-neutral-500">{item.reason || "No reason"} / {new Date(item.created_at).toLocaleString()}</p></div>) : <p className="text-sm text-neutral-500">No transitions recorded.</p>}</Section><Section title="Activity">{data.activity?.map((item) => <div className="border-t border-neutral-800 py-3 text-sm" key={item.id}><p>{item.description}</p><p className="text-neutral-500">{item.actor ?? "System"} / {new Date(item.created_at).toLocaleString()}</p></div>)}</Section>{!platform&&<BookingContractsSection bookingId={data.id} canManage={canManage}/>}<BookingProductionSection bookingId={data.id} canManage={canManage}/><BookingTravelSection bookingId={data.id} canManage={canManage}/><Section title="Call Sheet"><p className="mb-4 text-sm text-neutral-500">Build and publish the versioned operational document for this Booking.</p><Link className={buttonClass} href={`/workspace/bookings/${data.id}/call-sheet`}>Open Call Sheet</Link></Section>{data.currency!==undefined&&<BookingFinanceSection bookingId={data.id}/>} {!platform&&<EntityDocumentsSection entityType="booking" entityId={data.id}/>}</div>}</Frame>;
}
