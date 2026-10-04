"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { CheckCircle2, Clipboard, FileSignature, Filter, RefreshCw, Search, Send, Users } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { RouteGuard } from "@/components/auth/route-guard";
import { PageHeader, buttonClass, fieldClass, secondaryButtonClass, StatusBadge } from "@/components/ui/page";
import { useAuth } from "@/components/auth/auth-provider";
import { apiRequest } from "@/lib/api/client";

type Signer = { email: string; name?: string; status?: string };
type Event = { id: string; event_type: string; status: string; created_at: string };
type SourceOption = { id: string; title?: string; name?: string; reference?: string };
type BookingOption = { id: string; reference: string; title: string; event_date: string; artist?: { stage_name: string } };
type Item = {
  id: string; title: string; template_key: string; status: string; provider: string;
  source_document?: string | null; source_contract?: string | null;
  signers: Signer[]; signing_url?: string; completed_document_url?: string;
  last_event_at?: string | null; created_at?: string; events?: Event[];
};

const statuses = ["all", "draft", "ready", "sent", "viewed", "partially_signed", "completed", "declined", "expired"];
const statusLabel = (value: string) => value.replaceAll("_", " ");

function StatusPill({ value }: { value: string }) {
  const positive = value === "completed" || value === "sent";
  return <StatusBadge positive={positive}>{statusLabel(value)}</StatusBadge>;
}

export function SigningWorkspacePage({ initialDocument = "", initialContract = "" }: { initialDocument?: string; initialContract?: string }) {
  const { activeOrganizationId } = useAuth();
  const prefilledDocument = initialDocument;
  const prefilledContract = initialContract;
  const [items, setItems] = useState<Item[]>([]);
  const [selected, setSelected] = useState<Item | null>(null);
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [documents, setDocuments] = useState<SourceOption[]>([]);
  const [contracts, setContracts] = useState<SourceOption[]>([]);
  const [bookings, setBookings] = useState<BookingOption[]>([]);

  async function load() {
    if (!activeOrganizationId) return;
    setBusy(true);
    try { setItems(await apiRequest<Item[]>(`/api/signing/requests/?organization_id=${activeOrganizationId}`)); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Unable to load signing requests."); }
    finally { setBusy(false); }
  }

  useEffect(() => {
    if (!activeOrganizationId) return;
    void Promise.all([
      apiRequest<Item[]>(`/api/signing/requests/?organization_id=${activeOrganizationId}`),
      apiRequest<SourceOption[]>(`/api/documents/?organization_id=${activeOrganizationId}`),
      apiRequest<{ results: SourceOption[] }>(`/api/contracts/?organization_id=${activeOrganizationId}`),
      apiRequest<BookingOption[]>(`/api/bookings/?organization_id=${activeOrganizationId}`),
    ]).then(([requests, docs, contractResponse, bookingRows]) => { setItems(requests); setDocuments(docs); setContracts(contractResponse.results); setBookings(bookingRows); })
      .catch((error) => setMessage(error instanceof Error ? error.message : "Unable to load signing sources."));
  }, [activeOrganizationId]);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeOrganizationId) return;
    const form = new FormData(event.currentTarget);
    const signerLines = String(form.get("signers") || "").split(/[\n,]+/).map((value) => value.trim()).filter(Boolean);
    const signers = signerLines.map((line) => {
      const [email, ...name] = line.split("|").map((value) => value.trim());
      return { email, ...(name.length ? { name: name.join(" | ") } : {}) };
    });
    try {
      let sourceDocument = String(form.get("source_document") || "").trim() || null;
      const upload = form.get("document_file");
      if (upload instanceof File && upload.size > 0) {
        const uploadForm = new FormData();
        uploadForm.set("organization", activeOrganizationId);
        uploadForm.set("title", String(form.get("title") || upload.name));
        uploadForm.set("document_type", "contract");
        uploadForm.set("visibility", "private");
        uploadForm.set("file", upload);
        const document = await apiRequest<{ id: string }>("/api/documents/upload/", { method: "POST", body: uploadForm });
        sourceDocument = document.id;
      }
      await apiRequest("/api/signing/requests/", {
        method: "POST",
        body: JSON.stringify({
          organization_id: activeOrganizationId,
          title: form.get("title"),
          template_key: form.get("template_key"),
          booking: form.get("booking_id") || null,
          source_document: sourceDocument,
          source_contract: form.get("source_contract") || null,
          signers,
        }),
      });
      event.currentTarget.reset();
      setMessage("Signing request saved as a draft.");
      await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to create signing request."); }
  }

  async function open(item: Item) {
    try { setSelected(await apiRequest<Item>(`/api/signing/requests/${item.id}/`)); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Unable to load request details."); }
  }

  async function copyLink(url: string) {
    try { await navigator.clipboard.writeText(url); setMessage("Signing link copied."); }
    catch { setMessage("Unable to copy the signing link."); }
  }

  async function action(item: Item, value: "ready" | "send" | "cancel") {
    try {
      const updated = await apiRequest<Item>(`/api/signing/requests/${item.id}/action/`, { method: "POST", body: JSON.stringify({ action: value }) });
      setSelected(updated);
      setMessage(value === "ready" ? "Request marked ready." : value === "send" ? "Request sent through the self-hosted OpenSign service." : "Signing request cancelled.");
      await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to update signing request."); }
  }

  const visible = useMemo(() => items.filter((item) => {
    const matchesStatus = filter === "all" || item.status === filter;
    const needle = query.trim().toLowerCase();
    return matchesStatus && (!needle || item.title.toLowerCase().includes(needle) || item.signers.some((signer) => signer.email.toLowerCase().includes(needle)));
  }), [filter, items, query]);

  return <RouteGuard portal="workspace"><AppShell organizationScoped><main className="p-4 sm:p-8">
    <PageHeader eyebrow="Workspace / Signing" title="Signing workspace" description="Prepare, review, and monitor agreements. OpenSign events update request status through the secured webhook." actions={<span className="evolve-tool-button inline-flex items-center gap-2"><FileSignature size={16} /> OpenSign events enabled</span>} />
    <div className="mt-7 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {[
        ["Total requests", items.length, "all"],
        ["Awaiting signatures", items.filter((item) => ["ready", "sent", "viewed", "partially_signed"].includes(item.status)).length, "sent"],
        ["Completed", items.filter((item) => item.status === "completed").length, "completed"],
        ["Drafts", items.filter((item) => item.status === "draft").length, "draft"],
      ].map(([label, count, value]) => <button className={`evolve-panel p-4 text-left transition hover:-translate-y-0.5 ${filter === value ? "ring-2 ring-[var(--accent-strong)]" : ""}`} key={String(label)} onClick={() => setFilter(String(value))}><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{label}</p><p className="mt-2 text-2xl font-semibold">{count}</p></button>)}
    </div>
    <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
      <section className="evolve-panel overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-[var(--border)] p-5 lg:flex-row lg:items-center lg:justify-between">
          <div><h2 className="font-semibold">Requests</h2><p className="mt-1 text-sm text-[var(--text-muted)]">{visible.length} request{visible.length === 1 ? "" : "s"} shown</p></div>
          <div className="flex flex-wrap gap-2">
            <label className="relative"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" size={16} /><input className={`pl-9 ${fieldClass}`} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search title or signer" /></label>
            <button className={secondaryButtonClass} onClick={() => void load()} disabled={busy}><RefreshCw className={busy ? "animate-spin" : ""} size={15} /> Refresh</button>
          </div>
        </div>
        <div className="flex gap-2 overflow-x-auto border-b border-[var(--border)] p-3">
          {statuses.map((value) => <button className={`whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-semibold capitalize ${filter === value ? "bg-[var(--accent)] text-white" : "bg-[var(--surface-raised)] text-[var(--text-secondary)]"}`} key={value} onClick={() => setFilter(value)}><Filter className="mr-1 inline" size={12} />{statusLabel(value)}</button>)}
        </div>
        <div>{visible.map((item) => <button className="grid w-full gap-3 border-b border-[var(--border)] p-5 text-left transition hover:bg-[var(--background-soft)] sm:grid-cols-[minmax(0,1.5fr)_minmax(9rem,1fr)_auto] sm:items-center" key={item.id} onClick={() => void open(item)}><span><span className="block font-medium">{item.title}</span><span className="mt-1 block text-xs text-[var(--text-muted)]">{item.signers.length} signer{item.signers.length === 1 ? "" : "s"}{item.template_key ? `  -  ${item.template_key}` : ""}</span></span><span className="text-sm text-[var(--text-secondary)]">{item.last_event_at ? new Date(item.last_event_at).toLocaleDateString() : "No activity yet"}</span><StatusPill value={item.status} /></button>)}{!visible.length && <p className="p-10 text-center text-sm text-[var(--text-muted)]">No signing requests match this view.</p>}</div>
      </section>
      <form className="evolve-panel grid content-start gap-4 p-5" onSubmit={create}>
        <div><div className="flex items-center gap-2"><Send size={17} className="text-[var(--accent)]" /><h2 className="font-semibold">New signing request</h2></div><p className="mt-1 text-sm text-[var(--text-muted)]">Requests start as drafts until the provider sends them.</p></div>
        <label className="grid gap-2 text-sm font-medium text-[var(--text-secondary)]">Request title<input className={fieldClass} name="title" defaultValue={prefilledDocument ? "Document signing request" : prefilledContract ? "Contract signing request" : "Performance agreement"} placeholder="Performance agreement" required /></label>
        <label className="grid gap-2 text-sm font-medium text-[var(--text-secondary)]">Booking<select className={fieldClass} name="booking_id"><option value="">Link a Booking for automatic document matching</option>{bookings.map((booking) => <option key={booking.id} value={booking.id}>{booking.reference} · {booking.title} · {booking.event_date}</option>)}</select><span className="text-xs font-normal text-[var(--text-muted)]">When linked, the latest document and contract attached to the Booking are used if no source is selected.</span></label>
        <label className="grid gap-2 text-sm font-medium text-[var(--text-secondary)]">Template key<input className={fieldClass} name="template_key" placeholder="booking-agreement-v1" /><span className="text-xs font-normal text-[var(--text-muted)]">Optional mapping to a configured template.</span></label>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1"><label className="grid gap-2 text-sm font-medium text-[var(--text-secondary)]">Source document<select className={fieldClass} name="source_document" defaultValue={prefilledDocument}><option value="">Choose an uploaded document</option>{documents.map((document) => <option key={document.id} value={document.id}>{document.title || document.name || document.id}</option>)}</select></label><label className="grid gap-2 text-sm font-medium text-[var(--text-secondary)]">Source contract<select className={fieldClass} name="source_contract" defaultValue={prefilledContract}><option value="">Choose a contract</option>{contracts.map((contract) => <option key={contract.id} value={contract.id}>{contract.title || contract.reference || contract.id}</option>)}</select></label></div>
        <label className="grid gap-2 text-sm font-medium text-[var(--text-secondary)]">Upload document for signing<input className={fieldClass} name="document_file" type="file" accept="application/pdf,.doc,.docx" /><span className="text-xs font-normal text-[var(--text-muted)]">Stored privately and attached to this signing request.</span></label>
        <label className="grid gap-2 text-sm font-medium text-[var(--text-secondary)]">Signers<span className="text-xs font-normal text-[var(--text-muted)]">One email per line. Optional name format: email | Full name.</span><textarea className={fieldClass} name="signers" placeholder={"promoter@example.com | Promoter name"} required rows={5} /></label>
        <button className={buttonClass}><Send size={15} /> Save draft</button>
      </form>
    </div>
    {selected && <section className="evolve-panel mt-6 p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="evolve-eyebrow">Request details</p><h2 className="mt-1 text-xl font-semibold">{selected.title}</h2><div className="mt-2 flex flex-wrap items-center gap-2"><StatusPill value={selected.status} /><span className="text-sm text-[var(--text-muted)]">{selected.provider}</span></div></div><div className="flex flex-wrap gap-2">{selected.status === "draft" && <button className={buttonClass} onClick={() => void action(selected, "ready")}><CheckCircle2 size={15} /> Mark ready</button>}{selected.status === "ready" && <button className={buttonClass} onClick={() => void action(selected, "send")}><Send size={15} /> Send via OpenSign</button>}{["draft", "ready"].includes(selected.status) && <button className={secondaryButtonClass} onClick={() => void action(selected, "cancel")}>Cancel request</button>}<button className={secondaryButtonClass} onClick={() => setSelected(null)}>Close</button></div></div>
      <div className="mt-6 rounded-xl border border-stone-300 bg-[#fffdf8] p-6 text-stone-900 shadow-inner sm:p-10"><div className="mx-auto max-w-2xl border-b-2 border-stone-900 pb-5 text-center"><p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-stone-500">Evolve official document</p><h3 className="mt-3 font-serif text-2xl font-semibold">{selected.title}</h3><p className="mt-2 text-xs uppercase tracking-[0.16em] text-stone-500">Prepared for electronic signature</p></div><div className="mx-auto mt-6 max-w-2xl space-y-3 font-serif text-sm leading-7 text-stone-700"><p><strong>Parties.</strong> This document is prepared from the selected Evolve template and will be populated with the approved booking, promoter, artist, and signatory information.</p><p><strong>Execution.</strong> Signers receive the controlled signing link after the request is sent. The final completed document is retained with its signing status and event history.</p></div></div><div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1fr]">
        <div><h3 className="flex items-center gap-2 text-sm font-semibold"><Users size={16} /> Signers</h3><div className="mt-3 grid gap-2">{selected.signers.map((signer) => <div className="flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-3 text-sm" key={signer.email}><span>{signer.name || signer.email}<span className="block text-xs text-[var(--text-muted)]">{signer.email}</span></span><span className="capitalize text-xs text-[var(--text-secondary)]">{statusLabel(signer.status || "pending")}</span></div>)}</div></div>
        <div><h3 className="flex items-center gap-2 text-sm font-semibold"><CheckCircle2 size={16} /> Activity</h3><div className="mt-3 grid gap-2">{selected.events?.length ? selected.events.map((event) => <div className="rounded-lg border border-[var(--border)] p-3 text-sm" key={event.id}><p>{event.event_type}  -  {statusLabel(event.status)}</p><p className="mt-1 text-xs text-[var(--text-muted)]">{new Date(event.created_at).toLocaleString()}</p></div>) : <p className="text-sm text-[var(--text-muted)]">No provider events received yet.</p>}</div></div>
      </div>
      {(selected.signing_url || selected.completed_document_url) && <div className="mt-6 flex flex-wrap gap-2 border-t border-[var(--border)] pt-5">{selected.signing_url && <><a className={buttonClass} href={selected.signing_url} target="_blank" rel="noreferrer"><Send size={15} /> Open signing link</a><button className={secondaryButtonClass} onClick={() => void copyLink(selected.signing_url!)}><Clipboard size={15} /> Copy link</button></>}{selected.completed_document_url && <a className={secondaryButtonClass} href={selected.completed_document_url} target="_blank" rel="noreferrer">Open completed document</a>}</div>}
    </section>}
    {message && <p aria-live="polite" className="mt-4 text-sm text-[var(--accent-strong)]">{message}</p>}
  </main></AppShell></RouteGuard>;
}
