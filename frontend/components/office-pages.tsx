"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { RouteGuard } from "@/components/auth/route-guard";
import { useAuth } from "@/components/auth/auth-provider";
import { apiRequest } from "@/lib/api/client";

type Block = { type: string; text?: string; content?: Block[] };
type OfficeResponse = { document: string; title?: string; format: string | null; content_json: Block | null; revision_number: number };
type OfficeItem = { id: string; title: string; format: string; revision_number: number };

function Frame({ children }: { children: React.ReactNode }) {
  return <RouteGuard portal="workspace"><AppShell organizationScoped>{children}</AppShell></RouteGuard>;
}
function Nav() {
  return <nav className="mb-6 flex gap-4 text-sm text-neutral-400"><Link href="/workspace/office">Office</Link><Link href="/workspace/office/new">New</Link><Link href="/workspace/documents">Files</Link></nav>;
}
const initial: Block = { type: "doc", content: [{ type: "paragraph", content: [] }] };
function blockText(block: Block): string { return block.text ?? (block.content ?? []).map(blockText).join(" "); }

export function OfficeHomePage() {
  const { activeOrganizationId } = useAuth();
  const [items, setItems] = useState<OfficeItem[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { if (!activeOrganizationId) return; void apiRequest<OfficeItem[]>(`/api/office/documents/list/?organization_id=${activeOrganizationId}`).then(setItems).catch(() => setError("Unable to load Office documents.")); }, [activeOrganizationId]);
  return <Frame><main className="mx-auto max-w-6xl p-6"><Nav /><div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm uppercase tracking-widest text-amber-300">Evolve Office</p><h1 className="mt-2 text-3xl font-semibold">Documents, notes and checklists</h1><p className="mt-2 text-neutral-400">Structured, organization-scoped content inside Evolve.</p></div><Link href="/workspace/office/new" className="rounded-md bg-amber-300 px-4 py-2 font-medium text-black">New document</Link></div>{error && <p className="mt-6 text-red-300">{error}</p>}<section className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{items.map(item => <Link key={item.id} href={`/workspace/office/${item.id}`} className="rounded-lg border border-neutral-800 bg-neutral-900 p-5 hover:border-amber-300"><h2 className="font-semibold">{item.title}</h2><p className="mt-2 text-sm text-neutral-400">{item.format} · revision {item.revision_number}</p></Link>)}{!items.length && !error && <p className="text-neutral-400">No Office documents yet.</p>}</section></main></Frame>;
}

export function OfficeEditorPage({ id }: { id?: string }) {
  const { activeOrganizationId } = useAuth();
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [format, setFormat] = useState("document");
  const [content, setContent] = useState<Block>(initial);
  const [revision, setRevision] = useState(0);
  const [status, setStatus] = useState("");
  useEffect(() => { if (!id || !activeOrganizationId) return; void apiRequest<OfficeResponse>(`/api/documents/${id}/office-content/?organization_id=${activeOrganizationId}`).then(data => { setTitle(data.title ?? ""); setFormat(data.format ?? "document"); setContent(data.content_json ?? initial); setRevision(data.revision_number); }).catch(() => setStatus("Unable to load document.")); }, [id, activeOrganizationId]);
  async function save() { if (!activeOrganizationId) return; setStatus("Saving..."); try { if (!id) { const created = await apiRequest<OfficeResponse>("/api/office/documents/", { method: "POST", body: JSON.stringify({ organization_id: activeOrganizationId, title: title || "Untitled document", format, document_type: "other" }) }); router.push(`/workspace/office/${created.document}`); return; } const saved = await apiRequest<OfficeResponse>(`/api/documents/${id}/office-content/`, { method: "PATCH", body: JSON.stringify({ organization_id: activeOrganizationId, content_json: content, expected_revision: revision }) }); setRevision(saved.revision_number); setStatus("Saved"); } catch (error) { setStatus(error instanceof Error ? error.message : "Save failed."); } }
  function add(type: string) { setContent(previous => ({ ...previous, content: [...(previous.content ?? []), { type, content: [] }] })); setStatus("Unsaved"); }
  function update(index: number, text: string) { setContent(previous => ({ ...previous, content: (previous.content ?? []).map((block, i) => i === index ? { ...block, text } : block) })); setStatus("Unsaved"); }
  return <Frame><main className="mx-auto max-w-4xl p-6"><Nav /><div className="flex flex-wrap gap-3"><input aria-label="Document title" className="min-w-[16rem] flex-1 rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-xl" value={title} onChange={event => { setTitle(event.target.value); setStatus("Unsaved"); }} placeholder="Untitled document" /><select aria-label="Document type" className="rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2" value={format} onChange={event => setFormat(event.target.value)}><option value="document">Document</option><option value="note">Note</option><option value="checklist">Checklist</option><option value="sheet">Sheet</option></select><button className="rounded-md bg-amber-300 px-4 py-2 font-medium text-black" onClick={save}>{id ? "Save" : "Create"}</button></div><div className="mt-4 flex flex-wrap gap-2 text-sm"><button className="rounded border border-neutral-700 px-3 py-2" onClick={() => add("heading")}>Heading</button><button className="rounded border border-neutral-700 px-3 py-2" onClick={() => add("paragraph")}>Paragraph</button><button className="rounded border border-neutral-700 px-3 py-2" onClick={() => add("checklist")}>Checklist</button><span className="self-center text-neutral-400">{status || `Revision ${revision}`}</span></div><article className="mt-6 space-y-3 rounded-lg border border-neutral-800 bg-neutral-950 p-5">{(content.content ?? []).map((block, index) => <textarea key={`${index}-${block.type}`} aria-label={`${block.type} ${index + 1}`} className="min-h-20 w-full rounded border border-neutral-800 bg-neutral-900 p-3" value={blockText(block)} onChange={event => update(index, event.target.value)} placeholder={block.type} />)}</article><p className="mt-4 text-sm text-neutral-500">Server-confirmed revisions protect against stale saves. Native Office editing is structured JSON; offline editing is not enabled.</p></main></Frame>;
}
