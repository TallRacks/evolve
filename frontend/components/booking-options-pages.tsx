"use client";

import { FormEvent, useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { RouteGuard } from "@/components/auth/route-guard";
import { useAuth } from "@/components/auth/auth-provider";
import { apiRequest } from "@/lib/api/client";
import { hasOrganizationPermission } from "@/lib/auth/access";
import { buttonClass, fieldClass, PageHeader, secondaryButtonClass } from "@/components/ui/page";

type Option = { id: string; category: "performance" | "event"; name: string; is_active: boolean };
const groups: { category: Option["category"]; title: string; detail: string }[] = [
  { category: "performance", title: "Performance types", detail: "How the artist will perform." },
  { category: "event", title: "Event types", detail: "The format of the event." },
];

export function BookingOptionsPage() {
  const { activeOrganizationId, session } = useAuth();
  const [items, setItems] = useState<Option[]>([]);
  const [message, setMessage] = useState("");
  const canManage = hasOrganizationPermission(session, activeOrganizationId, "booking.manage");
  async function load() {
    if (!activeOrganizationId) return;
    try { setItems(await apiRequest<Option[]>(`/api/booking-options/?organization_id=${activeOrganizationId}&include_inactive=true`)); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Unable to load booking options."); }
  }
  useEffect(() => { if (!activeOrganizationId) return; void apiRequest<Option[]>(`/api/booking-options/?organization_id=${activeOrganizationId}&include_inactive=true`).then(setItems).catch((error) => setMessage(error instanceof Error ? error.message : "Unable to load booking options.")); }, [activeOrganizationId]);
  async function add(event: FormEvent<HTMLFormElement>, category: Option["category"]) {
    event.preventDefault();
    if (!activeOrganizationId) return;
    const form = new FormData(event.currentTarget);
    try {
      await apiRequest("/api/booking-options/", { method: "POST", body: JSON.stringify({ organization_id: activeOrganizationId, category, name: form.get("name") }) });
      event.currentTarget.reset(); setMessage("Booking option added."); await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to add option."); }
  }
  async function toggle(item: Option) {
    try { await apiRequest(`/api/booking-options/${item.id}/`, { method: "PATCH", body: JSON.stringify({ is_active: !item.is_active }) }); setMessage("Booking option updated."); await load(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Unable to update option."); }
  }
  return <RouteGuard portal="workspace"><AppShell organizationScoped><main className="p-4 sm:p-8">
    <PageHeader eyebrow="Booking settings" title="Booking options" description="Configure the performance and event types available when creating or editing bookings." />
    <div className="mt-7 grid gap-6 lg:grid-cols-2">{groups.map((group) => <section className="evolve-panel p-5" key={group.category}>
      <h2 className="text-lg font-semibold">{group.title}</h2><p className="mt-1 text-sm text-[var(--text-muted)]">{group.detail}</p>
      <div className="mt-4 grid gap-2">{items.filter((item) => item.category === group.category).map((item) => <div className={`flex items-center justify-between rounded-lg border px-3 py-2 text-sm ${item.is_active ? "border-[var(--border)]" : "border-dashed opacity-50"}`} key={item.id}><span>{item.name}</span>{canManage && <button className={secondaryButtonClass} onClick={() => void toggle(item)}>{item.is_active ? "Disable" : "Enable"}</button>}</div>)}</div>
      {canManage && <form className="mt-5 flex gap-2" onSubmit={(event) => void add(event, group.category)}><input className={fieldClass} name="name" placeholder={group.category === "performance" ? "e.g. Acoustic set" : "e.g. Private event"} required maxLength={80} /><button className={buttonClass}>Add</button></form>}
    </section>)}</div>{message && <p className="mt-4 text-sm">{message}</p>}
  </main></AppShell></RouteGuard>;
}
