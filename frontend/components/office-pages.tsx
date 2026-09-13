"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import LinkExtension from "@tiptap/extension-link";
import Underline from "@tiptap/extension-underline";
import { Table } from "@tiptap/extension-table";
import TableCell from "@tiptap/extension-table-cell";
import TableHeader from "@tiptap/extension-table-header";
import TableRow from "@tiptap/extension-table-row";
import TaskItem from "@tiptap/extension-task-item";
import TaskList from "@tiptap/extension-task-list";
import type { Editor } from "@tiptap/core";
import type { JSONContent } from "@tiptap/core";
import { AppShell } from "@/components/app-shell";
import { RouteGuard } from "@/components/auth/route-guard";
import { useAuth } from "@/components/auth/auth-provider";
import { apiRequest, ApiError } from "@/lib/api/client";

type OfficeResponse = { document: string; title?: string; format: string | null; content_json: JSONContent | null; revision_number: number; last_edited_at?: string };
type OfficeItem = { id: string; title: string; format: string; revision_number: number; visibility?: string; updated_at?: string };
type Revision = { id: string; revision_number: number; content_json: JSONContent; created_by: string | null; created_at: string; change_summary: string };

const initial: JSONContent = { type: "doc", content: [{ type: "paragraph" }] };
const extensions = [
  StarterKit.configure({ heading: { levels: [1, 2, 3] } }), Underline,
  LinkExtension.configure({ openOnClick: false, protocols: ["http", "https"] }),
  Table.configure({ resizable: true }), TableRow, TableHeader, TableCell,
  TaskList, TaskItem.configure({ nested: true }),
];

function Frame({ children }: { children: React.ReactNode }) {
  return <RouteGuard portal="workspace"><AppShell organizationScoped>{children}</AppShell></RouteGuard>;
}

function Nav() {
  return <nav aria-label="Office" className="mb-6 flex flex-wrap gap-4 text-sm text-neutral-400"><Link href="/workspace/office">Office</Link><Link href="/workspace/office/shared">Shared with me</Link><Link href="/workspace/office/recent">Recent</Link><Link href="/workspace/office/starred">Starred</Link><Link href="/workspace/office/new">New</Link><Link href="/workspace/documents">Files</Link></nav>;
}

function Toolbar({ editor }: { editor: Editor | null }) {
  if (!editor) return null;
  const action = (label: string, run: () => void, active = false) => <button type="button" aria-label={label} title={label} aria-pressed={active} className={`min-h-10 rounded border px-2 text-sm ${active ? "border-amber-300 text-amber-200" : "border-neutral-700 text-neutral-300"}`} onClick={run}>{label}</button>;
  return <div className="flex flex-wrap gap-2 border-b border-neutral-800 pb-3" role="toolbar" aria-label="Document formatting">
    {action("Bold", () => editor.chain().focus().toggleBold().run(), editor.isActive("bold"))}
    {action("Italic", () => editor.chain().focus().toggleItalic().run(), editor.isActive("italic"))}
    {action("Underline", () => editor.chain().focus().toggleUnderline().run(), editor.isActive("underline"))}
    {action("Strike", () => editor.chain().focus().toggleStrike().run(), editor.isActive("strike"))}
    {action("Heading 1", () => editor.chain().focus().toggleHeading({ level: 1 }).run(), editor.isActive("heading", { level: 1 }))}
    {action("Heading 2", () => editor.chain().focus().toggleHeading({ level: 2 }).run(), editor.isActive("heading", { level: 2 }))}
    {action("Heading 3", () => editor.chain().focus().toggleHeading({ level: 3 }).run(), editor.isActive("heading", { level: 3 }))}
    {action("Bulleted list", () => editor.chain().focus().toggleBulletList().run(), editor.isActive("bulletList"))}
    {action("Numbered list", () => editor.chain().focus().toggleOrderedList().run(), editor.isActive("orderedList"))}
    {action("Checklist", () => editor.chain().focus().toggleTaskList().run(), editor.isActive("taskList"))}
    {action("Quote", () => editor.chain().focus().toggleBlockquote().run(), editor.isActive("blockquote"))}
    {action("Divider", () => editor.chain().focus().setHorizontalRule().run())}
    {action("Table", () => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run())}
    {action("Undo", () => editor.chain().focus().undo().run())}
    {action("Redo", () => editor.chain().focus().redo().run())}
  </div>;
}

export function OfficeHomePage({ filter = "all" }: { filter?: "all" | "shared" | "recent" | "starred" }) {
  const { activeOrganizationId, activeWorkspaceId } = useAuth();
  const [items, setItems] = useState<OfficeItem[]>([]);
  const [error, setError] = useState("");
  const [starred, setStarred] = useState<string[]>([]);
  useEffect(() => { try { setStarred(JSON.parse(localStorage.getItem("evolve.office.starred") ?? "[]") as string[]); } catch { setStarred([]); } }, []);
  useEffect(() => { if (!activeOrganizationId) return; void apiRequest<OfficeItem[]>(`/api/office/documents/list/?organization_id=${activeOrganizationId}${activeWorkspaceId ? `&workspace_id=${activeWorkspaceId}` : ""}`).then((next) => {
    if (filter === "all") return setItems(next);
    try {
      const key = filter === "recent" ? "evolve.office.recent" : "evolve.office.starred";
      const ids = JSON.parse(localStorage.getItem(key) ?? "[]") as string[];
      setItems(next.filter((item) => filter === "shared" ? item.visibility !== "restricted" : ids.includes(item.id)));
    } catch { setItems([]); }
  }).catch(() => setError("Unable to load Office documents.")); }, [activeOrganizationId, activeWorkspaceId, filter]);
  function toggleStar(id: string) { const next = starred.includes(id) ? starred.filter((item) => item !== id) : [id, ...starred]; setStarred(next); localStorage.setItem("evolve.office.starred", JSON.stringify(next)); if (filter === "starred") setItems((current) => current.filter((item) => next.includes(item.id))); }
  const title = filter === "all" ? "Documents, notes and checklists" : filter === "shared" ? "Shared with me" : filter[0].toUpperCase() + filter.slice(1);
  return <Frame><main className="mx-auto max-w-6xl p-4 sm:p-6"><Nav /><div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm uppercase tracking-widest text-amber-300">Evolve Office</p><h1 className="mt-2 text-3xl font-semibold">{title}</h1><p className="mt-2 text-neutral-400">Structured, organization-scoped collaboration content.</p></div><div className="flex flex-wrap gap-2"><Link href="/workspace/office/new" className="rounded-md bg-amber-300 px-4 py-2 font-medium text-black">New document</Link><Link href="/workspace/office/new?format=sheet" className="rounded-md border border-neutral-700 px-4 py-2">New sheet</Link></div></div>{filter === "all" && <div className="mt-8 grid gap-3 sm:grid-cols-4"><Link className="rounded-lg border border-neutral-800 p-4 hover:border-amber-300" href="/workspace/office/new?format=document">New Document</Link><Link className="rounded-lg border border-neutral-800 p-4 hover:border-amber-300" href="/workspace/office/new?format=sheet">New Sheet</Link><Link className="rounded-lg border border-neutral-800 p-4 hover:border-amber-300" href="/workspace/office/new?format=note">New Note</Link><Link className="rounded-lg border border-neutral-800 p-4 hover:border-amber-300" href="/workspace/office/new?format=checklist">New Checklist</Link></div>}{error && <p role="alert" className="mt-6 text-red-300">{error}</p>}<section className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{items.map((item) => <article key={item.id} className="rounded-lg border border-neutral-800 bg-neutral-900 p-5 hover:border-amber-300"><div className="flex items-start justify-between gap-3"><Link className="min-w-0 flex-1" href={`/workspace/office/${item.id}`} onClick={() => { const old = JSON.parse(localStorage.getItem("evolve.office.recent") ?? "[]") as string[]; localStorage.setItem("evolve.office.recent", JSON.stringify([item.id, ...old.filter((id) => id !== item.id)].slice(0, 50))); }}><h2 className="font-semibold">{item.title}</h2><p className="mt-2 text-sm text-neutral-400">{item.format} · revision {item.revision_number}</p></Link><button type="button" aria-label={starred.includes(item.id) ? "Unstar document" : "Star document"} className="text-xl text-amber-300" onClick={() => toggleStar(item.id)}>{starred.includes(item.id) ? "★" : "☆"}</button></div></article>)}{!items.length && !error && <p className="text-neutral-400">No Office documents in this view.</p>}</section></main></Frame>;
}

export function OfficeEditorPage({ id }: { id?: string }) {
  const { activeOrganizationId, activeWorkspaceId } = useAuth();
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [format, setFormat] = useState("document");
  const [revision, setRevision] = useState(0);
  const [status, setStatus] = useState<"Saved" | "Saving" | "Unsaved" | "Conflict" | "Error" | "Loading">("Loading");
  const [historyOpen, setHistoryOpen] = useState(false);
  const editor = useEditor({ extensions, content: initial, immediatelyRender: false, onUpdate: () => setStatus("Unsaved") });
  useEffect(() => { const requested = new URLSearchParams(window.location.search).get("format"); if (!id && requested && ["document", "note", "checklist", "sheet"].includes(requested)) setFormat(requested); }, [id]);
  useEffect(() => { if (!id || !activeOrganizationId || !editor) return; void apiRequest<OfficeResponse>(`/api/documents/${id}/office-content/?organization_id=${activeOrganizationId}${activeWorkspaceId ? `&workspace_id=${activeWorkspaceId}` : ""}`).then((data) => { setTitle(data.title ?? ""); setFormat(data.format ?? "document"); setRevision(data.revision_number); editor.commands.setContent(data.content_json ?? initial); setStatus("Saved"); }).catch(() => setStatus("Error")); }, [id, activeOrganizationId, activeWorkspaceId, editor]);
  async function save() { if (!activeOrganizationId || !editor) return; setStatus("Saving"); try { if (!id) { const created = await apiRequest<OfficeResponse>("/api/office/documents/", { method: "POST", body: JSON.stringify({ organization_id: activeOrganizationId, workspace_id: activeWorkspaceId, title: title || "Untitled document", format, document_type: "other" }) }); router.push(`/workspace/office/${created.document}`); return; } const saved = await apiRequest<OfficeResponse>(`/api/documents/${id}/office-content/`, { method: "PATCH", body: JSON.stringify({ organization_id: activeOrganizationId, workspace_id: activeWorkspaceId, content_json: editor.getJSON(), expected_revision: revision }) }); setRevision(saved.revision_number); setStatus("Saved"); } catch (error) { setStatus(error instanceof ApiError && error.status === 409 ? "Conflict" : "Error"); } }
  useEffect(() => { if (!id || status !== "Unsaved") return; const timer = window.setTimeout(() => void save(), 1800); return () => window.clearTimeout(timer); });
  useEffect(() => { function key(event: KeyboardEvent) { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") { event.preventDefault(); void save(); } } window.addEventListener("keydown", key); return () => window.removeEventListener("keydown", key); });
  const tone = useMemo(() => status === "Saved" ? "text-emerald-300" : status === "Conflict" || status === "Error" ? "text-red-300" : "text-amber-200", [status]);
  return <Frame><main className="mx-auto max-w-5xl p-4 sm:p-6"><Nav /><div className="flex flex-wrap gap-3"><input aria-label="Document title" className="min-w-[16rem] flex-1 rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-xl" value={title} onChange={(event) => { setTitle(event.target.value); setStatus("Unsaved"); }} placeholder="Untitled document" /><select aria-label="Document format" className="rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2" value={format} onChange={(event) => { setFormat(event.target.value); setStatus("Unsaved"); }}><option value="document">Document</option><option value="note">Note</option><option value="checklist">Checklist</option><option value="sheet">Sheet</option></select><button type="button" className="rounded-md bg-amber-300 px-4 py-2 font-medium text-black" onClick={() => void save()}>{id ? "Save" : "Create"}</button>{id && <button type="button" className="rounded-md border border-neutral-700 px-4 py-2" onClick={() => setHistoryOpen((value) => !value)}>Version history</button>}</div><div className="mt-4 flex items-center gap-3 text-sm"><span className={tone} role="status">{status}</span><span className="text-neutral-500">Revision {revision} · autosaves after 1.8s idle</span></div>{status === "Conflict" && <div className="mt-4 rounded border border-red-900 bg-red-950/40 p-3 text-sm text-red-200">This document changed since you opened it. Reload Latest or save a copy after reviewing.</div>}{status === "Error" && <div className="mt-4 rounded border border-red-900 bg-red-950/40 p-3 text-sm text-red-200">Unable to save. Your current editor content is preserved in memory. <button type="button" className="underline" onClick={() => void save()}>Retry</button></div>}{historyOpen && id && <VersionHistory documentId={id} organizationId={activeOrganizationId} onRestored={(data) => { setRevision(data.revision_number); editor?.commands.setContent(data.content_json ?? initial); setStatus("Saved"); }} />}{format === "sheet" ? <SheetFallback /> : <div className="mt-6 rounded-lg border border-neutral-800 bg-neutral-950 p-4"><Toolbar editor={editor} /><EditorContent editor={editor} className="office-editor mt-4 min-h-[28rem]" /></div>}<p className="mt-4 text-sm text-neutral-500">Structured JSON is validated server-side. Offline edits are not queued or cached.</p></main></Frame>;
}

function VersionHistory({ documentId, organizationId, onRestored }: { documentId: string; organizationId: string | null; onRestored: (data: OfficeResponse) => void }) {
  const [rows, setRows] = useState<Revision[]>([]); const [preview, setPreview] = useState<Revision | null>(null);
  useEffect(() => { if (organizationId) void apiRequest<Revision[]>(`/api/documents/${documentId}/office-revisions/?organization_id=${organizationId}`).then(setRows); }, [documentId, organizationId]);
  async function restore(revision: number) { if (!organizationId) return; const data = await apiRequest<OfficeResponse>(`/api/documents/${documentId}/office-revisions/${revision}/restore/`, { method: "POST", body: JSON.stringify({ organization_id: organizationId }) }); onRestored(data); }
  return <section aria-label="Version history" className="mt-5 rounded-lg border border-neutral-800 bg-neutral-900 p-4"><h2 className="font-semibold">Version history</h2>{rows.length ? <div className="mt-3 space-y-2">{rows.map((row) => <div key={row.revision_number} className="border-t border-neutral-800 py-3"><div className="flex flex-wrap items-center justify-between gap-3"><span>Revision {row.revision_number}<span className="ml-2 text-sm text-neutral-500">{new Date(row.created_at).toLocaleString()}</span></span><div className="flex gap-2"><button type="button" className="rounded border border-neutral-700 px-3 py-1 text-sm" onClick={() => setPreview(row)}>Preview</button><button type="button" className="rounded border border-neutral-700 px-3 py-1 text-sm" onClick={() => void restore(row.revision_number)}>Restore</button></div></div>{preview?.revision_number === row.revision_number && <pre className="mt-3 max-h-48 overflow-auto rounded bg-neutral-950 p-3 text-xs text-neutral-400">Viewing Revision {row.revision_number}{"\n"}{JSON.stringify(row.content_json, null, 2)}</pre>}</div>)}</div> : <p className="mt-3 text-sm text-neutral-500">No immutable checkpoints yet.</p>}</section>;
}

function SheetFallback() {
  const [rows, setRows] = useState<string[][]>([["", "", ""], ["", "", ""], ["", "", ""]]);
  function update(row: number, column: number, value: string) { setRows((current) => current.map((item, i) => i === row ? item.map((cell, j) => j === column ? value : cell) : item)); }
  return <section aria-label="Sheet grid" className="mt-6 overflow-x-auto rounded-lg border border-neutral-800 bg-neutral-950"><div className="min-w-[38rem]"><div className="grid grid-cols-3 border-b border-neutral-800 bg-neutral-900 text-sm text-neutral-400">{["A", "B", "C"].map((column) => <div key={column} className="p-3 font-medium">{column}</div>)}</div>{rows.map((row, rowIndex) => <div key={rowIndex} className="grid grid-cols-3 border-b border-neutral-900">{row.map((cell, columnIndex) => <input key={`${rowIndex}-${columnIndex}`} aria-label={`Row ${rowIndex + 1} column ${columnIndex + 1}`} className="min-w-0 border-r border-neutral-900 bg-transparent p-3 outline-none focus:bg-neutral-900 focus:ring-1 focus:ring-amber-300" value={cell} onChange={(event) => update(rowIndex, columnIndex, event.target.value)} />)}</div>)}</div><p className="p-3 text-sm text-neutral-500">Typed columns, CSV import/export, and server-persisted grid data require the next Sheets backend slice.</p></section>;
}
