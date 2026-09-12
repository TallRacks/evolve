"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth/auth-provider";
import { RouteGuard } from "@/components/auth/route-guard";
import { apiRequest } from "@/lib/api/client";
import { hasOrganizationPermission } from "@/lib/auth/access";
import { buttonClass, fieldClass, PageHeader, secondaryButtonClass } from "@/components/ui/page";

type Option = { id: string; name: string; city?: string; country?: string; timezone?: string };

const presets = {
  minimal: { label: "Minimal", detail: "Booking only", prepare_production: false, prepare_call_sheet: false, prepare_travel: false },
  standard: { label: "Standard show", detail: "Production, draft Call Sheet, standard tasks", prepare_production: true, prepare_call_sheet: true, prepare_travel: false },
  tour: { label: "Tour date", detail: "Production, Call Sheet, and Travel shell", prepare_production: true, prepare_call_sheet: true, prepare_travel: true },
  festival: { label: "Festival", detail: "Production, Call Sheet, festival checklist", prepare_production: true, prepare_call_sheet: true, prepare_travel: false },
} as const;

function slugify(value: string) { return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 130) || `record-${Date.now()}`; }

export function BookingQuickCreatePage() {
  const router = useRouter();
  const { activeOrganizationId, session } = useAuth();
  const canManage = hasOrganizationPermission(session, activeOrganizationId, "booking.manage");
  const [artists, setArtists] = useState<Option[]>([]);
  const [venues, setVenues] = useState<Option[]>([]);
  const [promoters, setPromoters] = useState<Option[]>([]);
  const [preset, setPreset] = useState<keyof typeof presets>("standard");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [quickVenue, setQuickVenue] = useState(false);
  const [quickPromoter, setQuickPromoter] = useState(false);
  const [selectedVenueId, setSelectedVenueId] = useState("");
  const [selectedPromoterId, setSelectedPromoterId] = useState("");

  useEffect(() => {
    if (!activeOrganizationId) return;
    const query = `?organization_id=${activeOrganizationId}`;
    Promise.all([
      apiRequest<Option[]>(`/api/artists/${query}`),
      apiRequest<Option[]>(`/api/venues/${query}`),
      apiRequest<Option[]>(`/api/promoters/${query}`),
    ]).then(([nextArtists, nextVenues, nextPromoters]) => { setArtists(nextArtists); setVenues(nextVenues); setPromoters(nextPromoters); }).catch(() => setError("Unable to load booking options."));
  }, [activeOrganizationId]);

  async function createVenue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeOrganizationId) return;
    const form = new FormData(event.currentTarget);
    try {
      const venue = await apiRequest<Option>("/api/venues/", { method: "POST", body: JSON.stringify({ organization_id: activeOrganizationId, name: form.get("name"), slug: slugify(String(form.get("name"))), city: form.get("city"), country: form.get("country"), timezone: form.get("timezone") || "Africa/Johannesburg" }) });
      setVenues((current) => [...current, venue]);
      setQuickVenue(false);
      setSelectedVenueId(venue.id);
      setMessage("Venue created. It is selected below.");
      (document.querySelector("select[name=venue_id]") as HTMLSelectElement | null)?.setAttribute("data-new-value", venue.id);
    } catch { setError("Unable to create venue."); }
  }

  async function createPromoter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeOrganizationId) return;
    const form = new FormData(event.currentTarget);
    try {
      const promoter = await apiRequest<Option>("/api/promoters/", { method: "POST", body: JSON.stringify({ organization_id: activeOrganizationId, name: form.get("name"), slug: slugify(String(form.get("name"))), email: form.get("email") || "" }) });
      setPromoters((current) => [...current, promoter]);
      setQuickPromoter(false);
      setSelectedPromoterId(promoter.id);
      setMessage("Promoter created. Select it below.");
    } catch { setError("Unable to create promoter."); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeOrganizationId) return;
    const form = new FormData(event.currentTarget);
    const selected = presets[preset];
    try {
      const booking = await apiRequest<{ id: string }>("/api/bookings/", { method: "POST", body: JSON.stringify({ organization_id: activeOrganizationId, title: form.get("title"), artist_id: form.get("artist_id"), venue_id: form.get("venue_id") || null, promoter_id: form.get("promoter_id") || null, city_snapshot: form.get("city_snapshot") || "", event_date: form.get("event_date"), event_start_datetime: form.get("event_start_datetime") || null, timezone: form.get("timezone") || "Africa/Johannesburg", priority: form.get("priority") || "normal", prepare_production: selected.prepare_production, prepare_call_sheet: selected.prepare_call_sheet, prepare_travel: selected.prepare_travel }) });
      router.push(`/workspace/bookings/${booking.id}?created=1`);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to create booking."); }
  }

  return <RouteGuard portal="workspace"><AppShell organizationScoped><main className="p-4 sm:p-8"><PageHeader eyebrow="Live operations" title="New booking" description="Start with the show essentials. Add commercial, production, travel, and contract detail when you are ready." /><div className="mt-6 max-w-4xl">{error && <p className="mb-4 rounded-md border border-red-900 p-3 text-sm text-red-200">{error}</p>}{message && <p className="mb-4 rounded-md border border-emerald-900 p-3 text-sm text-emerald-200">{message}</p>}{!canManage ? <p className="rounded-md border border-amber-900 p-4 text-sm text-amber-200">You do not have permission to create bookings.</p> : <><form id="booking-essentials" className="grid gap-6" onSubmit={submit}><section className="rounded-xl border border-neutral-800 bg-neutral-950 p-5"><h2 className="text-lg font-semibold">Show essentials</h2><p className="mt-1 text-sm text-neutral-500">Four required decisions get the booking into your workspace.</p><div className="mt-5 grid gap-4 sm:grid-cols-2"><label className="grid gap-2 text-sm sm:col-span-2">Event / show name<input className={fieldClass} name="title" placeholder="Cape Town launch show" required /></label><label className="grid gap-2 text-sm">Artist<select className={fieldClass} name="artist_id" required><option value="">Select artist</option>{artists.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="grid gap-2 text-sm">Event date<input className={fieldClass} name="event_date" type="date" required /></label><label className="grid gap-2 text-sm">Time if known<input className={fieldClass} name="event_start_datetime" type="datetime-local" /></label><label className="grid gap-2 text-sm">Timezone<input className={fieldClass} name="timezone" defaultValue="Africa/Johannesburg" /></label><label className="grid gap-2 text-sm">Venue<select className={fieldClass} name="venue_id" value={selectedVenueId} onChange={(event) => setSelectedVenueId(event.target.value)}><option value="">Venue to be confirmed</option>{venues.map((item) => <option key={item.id} value={item.id}>{item.name}{item.city ? ` · ${item.city}` : ""}</option>)}</select></label><label className="grid gap-2 text-sm">City if venue is unknown<input className={fieldClass} name="city_snapshot" placeholder="Johannesburg" /></label><label className="grid gap-2 text-sm">Promoter <select className={fieldClass} name="promoter_id" value={selectedPromoterId} onChange={(event) => setSelectedPromoterId(event.target.value)}><option value="">Optional</option>{promoters.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="grid gap-2 text-sm">Priority<select className={fieldClass} name="priority" defaultValue="normal"><option>normal</option><option>high</option><option>urgent</option><option>low</option></select></label></div><div className="mt-4 flex flex-wrap gap-2"><button className={secondaryButtonClass} type="button" onClick={() => setQuickVenue((value) => !value)}>+ Quick-create venue</button><button className={secondaryButtonClass} type="button" onClick={() => setQuickPromoter((value) => !value)}>+ Quick-create promoter</button></div></section></form>{quickVenue && <section className="rounded-xl border border-amber-900/60 bg-amber-950/10 p-5"><h2 className="font-semibold">Quick-create venue</h2><form className="mt-4 grid gap-3 sm:grid-cols-4" onSubmit={createVenue}><input className={fieldClass} name="name" placeholder="Venue name" required /><input className={fieldClass} name="city" placeholder="City" required /><input className={fieldClass} name="country" placeholder="Country" required /><button className={buttonClass}>Create venue</button></form></section>}{quickPromoter && <section className="rounded-xl border border-amber-900/60 bg-amber-950/10 p-5"><h2 className="font-semibold">Quick-create promoter</h2><form className="mt-4 grid gap-3 sm:grid-cols-3" onSubmit={createPromoter}><input className={fieldClass} name="name" placeholder="Promoter name" required /><input className={fieldClass} name="email" placeholder="Optional email" type="email" /><button className={buttonClass}>Create promoter</button></form></section>}<section className="grid gap-6"><section className="rounded-xl border border-neutral-800 bg-neutral-950 p-5"><h2 className="font-semibold">Booking setup</h2><p className="mt-1 text-sm text-neutral-500">Choose what Evolve should prepare. Nothing creates a contract, invoice, or payment.</p><div className="mt-4 grid gap-3 sm:grid-cols-2">{Object.entries(presets).map(([value, option]) => <label className={`cursor-pointer rounded-lg border p-4 ${preset === value ? "border-amber-400 bg-amber-950/20" : "border-neutral-800"}`} key={value}><input className="sr-only" type="radio" name="preset" value={value} checked={preset === value} onChange={() => setPreset(value as keyof typeof presets)} /><span className="font-medium">{option.label}</span><span className="mt-1 block text-sm text-neutral-500">{option.detail}</span></label>)}</div></section><div className="flex flex-wrap gap-3"><button className={buttonClass} type="button" onClick={() => (document.getElementById("booking-essentials") as HTMLFormElement | null)?.requestSubmit()}>Create booking</button><button className={secondaryButtonClass} type="button" onClick={() => router.back()}>Cancel</button></div></section></>}</div></main></AppShell></RouteGuard>;
}
