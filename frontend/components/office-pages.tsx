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
import { Node } from "@tiptap/core";
import type { Editor } from "@tiptap/core";
import type { JSONContent } from "@tiptap/core";
import { AppShell } from "@/components/app-shell";
import { RouteGuard } from "@/components/auth/route-guard";
import { useAuth } from "@/components/auth/auth-provider";
import { apiRequest, ApiError } from "@/lib/api/client";

type OfficeResponse = { document: string; title?: string; format: string | null; content_json: JSONContent | null; revision_number: number; last_edited_at?: string };
type OfficeItem = { id: string; title: string; format: string; revision_number: number; visibility?: string; updated_at?: string };
type Revision = { id: string; revision_number: number; content_json: JSONContent; created_by: string | null; created_at: string; change_summary: string };

const PrivateImage = Node.create({
  name: "privateImage", group: "block", atom: true,
  addAttributes: () => ({ attachment_id: { default: null }, alt: { default: "" }, office_document_id: { default: null } }),
  parseHTML: () => [{ tag: "img[data-office-attachment]" }],
  renderHTML: ({ HTMLAttributes }) => ["img", { "data-office-attachment": HTMLAttributes.attachment_id, src: `/api/documents/${HTMLAttributes.office_document_id}/office-attachments/${HTMLAttributes.attachment_id}/preview/`, alt: HTMLAttributes.alt || "Attached image" }],
});

const initial: JSONContent = { type: "doc", content: [{ type: "paragraph" }] };
const extensions = [
  StarterKit.configure({ heading: { levels: [1, 2, 3] } }), Underline,
  LinkExtension.configure({ openOnClick: false, protocols: ["http", "https"] }),
  Table.configure({ resizable: true }), TableRow, TableHeader, TableCell,
  TaskList, TaskItem.configure({ nested: true }), PrivateImage,
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

export function OfficeHomePage({ filter = "all" }: { filter?: "all" | "shared" | "recent" | "starred" | "archived" }) {
  const { activeOrganizationId, activeWorkspaceId } = useAuth();
  const [items, setItems] = useState<OfficeItem[]>([]);
  const [error, setError] = useState("");
  const [starred, setStarred] = useState<string[]>(() => {
    if (typeof window === "undefined") return [];
    try { return JSON.parse(localStorage.getItem("evolve.office.starred") ?? "[]") as string[]; } catch { return []; }
  });
  useEffect(() => { if (!activeOrganizationId) return; void apiRequest<OfficeItem[]>(`/api/office/documents/list/?organization_id=${activeOrganizationId}${activeWorkspaceId ? `&workspace_id=${activeWorkspaceId}` : ""}${filter === "archived" ? "&status=archived" : "&status=active"}`).then((next) => {
    if (filter === "all" || filter === "archived") return setItems(next);
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


function OfficeAttachments({ documentId, organizationId, editor }: { documentId: string; organizationId: string | null; editor: Editor | null }) {
  const [items, setItems] = useState<Array<{ id: string; document_id: string; title: string; filename: string; is_image: boolean; preview_url: string | null; download_url: string }>>([]);
  const [message, setMessage] = useState("");
  const load = () => organizationId && void apiRequest<typeof items>(`/api/documents/${documentId}/office-attachments/?organization_id=${organizationId}`).then(setItems).catch(() => setMessage("Unable to load attachments."));
  useEffect(() => { load(); }, [documentId, organizationId]);
  async function upload(event: React.FormEvent<HTMLFormElement>) { event.preventDefault(); if (!organizationId) return; const formElement = event.currentTarget; const form = new FormData(formElement); try { await apiRequest(`/api/documents/${documentId}/office-attachments/?organization_id=${organizationId}`, { method: "POST", body: form }); formElement.reset(); setMessage("Attachment added."); load(); } catch (error) { setMessage(error instanceof Error ? error.message : "Attachment upload failed."); } }
  async function remove(id: string) { if (!organizationId) return; try { await apiRequest(`/api/documents/${documentId}/office-attachments/${id}/?organization_id=${organizationId}`, { method: "DELETE" }); load(); } catch { setMessage("Unable to remove attachment reference."); } }
  function insert(item: typeof items[number]) { if (!editor || !item.is_image) return; editor.chain().focus().insertContent({ type: "privateImage", attrs: { attachment_id: item.id, office_document_id: documentId, alt: item.title } }).run(); }
  return <section aria-label="Attachments" className="mt-6 rounded-lg border border-neutral-800 bg-neutral-950 p-4"><h2 className="font-semibold">Attachments</h2>{message && <p role="status" className="mt-2 text-sm text-amber-200">{message}</p>}<form className="mt-3 flex flex-wrap gap-2" onSubmit={(event) => void upload(event)}><input aria-label="Upload attachment" name="file" type="file" required className="max-w-full text-sm"/><label className="flex items-center gap-2 text-sm"><input name="is_image" type="checkbox"/> Image embed</label><button className="rounded border border-neutral-700 px-3 py-2 text-sm">Upload Attachment</button></form><div className="mt-4 grid gap-2">{items.map((item) => <div className="flex flex-wrap items-center justify-between gap-2 border-t border-neutral-800 pt-2 text-sm" key={item.id}><span>{item.filename || item.title}</span><span className="flex gap-2"><a className="underline" href={item.download_url}>Download</a>{item.is_image && <button type="button" className="underline" onClick={() => insert(item)}>Insert Image</button>}<button type="button" className="text-red-300 underline" onClick={() => void remove(item.id)}>Remove reference</button></span></div>)}</div></section>;
}

function DocumentTools({ editor }: { editor: Editor | null }) {
  const [query, setQuery] = useState("");
  const [replacement, setReplacement] = useState("");
  if (!editor) return null;
  const text = editor.getText();
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  const headings: Array<{ level: number; text: string; position: number }> = [];
  editor.state.doc.descendants((node, position) => {
    if (node.type.name === "heading") headings.push({ level: Number(node.attrs.level), text: node.textContent, position });
  });
  function replaceCurrent() {
    if (!query) return;
    const matches: Array<{ from: number; to: number; marks: typeof editor.state.schema.marks }> = [];
    editor.state.doc.descendants((node, position) => {
      if (!node.isText || !node.text) return;
      let offset = node.text.indexOf(query);
      while (offset !== -1) {
        matches.push({ from: position + offset, to: position + offset + query.length, marks: node.marks });
        offset = node.text.indexOf(query, offset + query.length);
      }
    });
    const transaction = editor.state.tr;
    for (const match of matches.reverse()) transaction.replaceWith(match.from, match.to, replacement ? editor.state.schema.text(replacement, match.marks) : []);
    if (matches.length) editor.view.dispatch(transaction);
  }
  return <div className="mt-4 grid gap-3 rounded border border-neutral-800 bg-neutral-900 p-3 text-sm sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]" aria-label="Document tools">
    <div><span className="text-neutral-400">{words} words · {text.length} characters</span><button type="button" className="ml-3 underline" onClick={() => window.print()}>Print</button></div>
    <details><summary className="cursor-pointer">Find / replace</summary><div className="mt-2 flex flex-wrap gap-2"><input aria-label="Find in document" className="rounded border border-neutral-700 bg-neutral-950 px-2 py-1" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find"/><input aria-label="Replace in document" className="rounded border border-neutral-700 bg-neutral-950 px-2 py-1" value={replacement} onChange={(event) => setReplacement(event.target.value)} placeholder="Replace with"/><button type="button" className="rounded border border-neutral-700 px-2 py-1" onClick={replaceCurrent}>Replace all</button></div></details>
    {headings.length > 0 && <details className="sm:col-span-2"><summary className="cursor-pointer">Outline ({headings.length})</summary><nav aria-label="Document outline" className="mt-2 grid gap-1">{headings.map((heading, index) => <button type="button" className="text-left text-neutral-300 hover:text-amber-300" style={{ paddingLeft: `${(heading.level - 1) * 0.75}rem` }} key={`${heading.text}-${index}`} onClick={() => { editor.commands.setTextSelection(heading.position); editor.commands.scrollIntoView(); }}>{heading.text || `Heading ${index + 1}`}</button>)}</nav></details>}
  </div>;
}

export function OfficeEditorPage({ id }: { id?: string }) {
  const { activeOrganizationId, activeWorkspaceId } = useAuth();
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [format, setFormat] = useState(() => {
    if (typeof window === "undefined") return "document";
    const requested = new URLSearchParams(window.location.search).get("format");
    return requested && ["document", "note", "checklist", "sheet"].includes(requested) ? requested : "document";
  });
  const [revision, setRevision] = useState(0);
  const [status, setStatus] = useState<"Saved" | "Saving" | "Unsaved" | "Conflict" | "Error" | "Loading">("Loading");
  const [historyOpen, setHistoryOpen] = useState(false);
  const editor = useEditor({ extensions, content: initial, immediatelyRender: false, onUpdate: () => setStatus("Unsaved") });
  useEffect(() => { if (!id || !activeOrganizationId || !editor) return; void apiRequest<OfficeResponse>(`/api/documents/${id}/office-content/?organization_id=${activeOrganizationId}${activeWorkspaceId ? `&workspace_id=${activeWorkspaceId}` : ""}`).then((data) => { setTitle(data.title ?? ""); setFormat(data.format ?? "document"); setRevision(data.revision_number); editor.commands.setContent(data.content_json ?? initial); setStatus("Saved"); }).catch(() => setStatus("Error")); }, [id, activeOrganizationId, activeWorkspaceId, editor]);
  async function save() { if (!activeOrganizationId || !editor) return; setStatus("Saving"); try { if (!id) { const created = await apiRequest<OfficeResponse>("/api/office/documents/", { method: "POST", body: JSON.stringify({ organization_id: activeOrganizationId, workspace_id: activeWorkspaceId, title: title || "Untitled document", format, document_type: "other" }) }); router.push(`/workspace/office/${created.document}`); return; } const saved = await apiRequest<OfficeResponse>(`/api/documents/${id}/office-content/`, { method: "PATCH", body: JSON.stringify({ organization_id: activeOrganizationId, workspace_id: activeWorkspaceId, content_json: editor.getJSON(), expected_revision: revision }) }); setRevision(saved.revision_number); setStatus("Saved"); } catch (error) { setStatus(error instanceof ApiError && error.status === 409 ? "Conflict" : "Error"); } }
  useEffect(() => { if (!id || status !== "Unsaved") return; const timer = window.setTimeout(() => void save(), 1800); return () => window.clearTimeout(timer); });
  useEffect(() => { function key(event: KeyboardEvent) { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") { event.preventDefault(); void save(); } } window.addEventListener("keydown", key); return () => window.removeEventListener("keydown", key); });
  const tone = useMemo(() => status === "Saved" ? "text-emerald-300" : status === "Conflict" || status === "Error" ? "text-red-300" : "text-amber-200", [status]);
  return <Frame><main className="mx-auto max-w-5xl p-4 sm:p-6"><Nav /><div className="flex flex-wrap gap-3"><input aria-label="Document title" className="min-w-[16rem] flex-1 rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-xl" value={title} onChange={(event) => { setTitle(event.target.value); setStatus("Unsaved"); }} placeholder="Untitled document" /><select aria-label="Document format" className="rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2" value={format} onChange={(event) => { setFormat(event.target.value); setStatus("Unsaved"); }}><option value="document">Document</option><option value="note">Note</option><option value="checklist">Checklist</option><option value="sheet">Sheet</option></select><button type="button" className="rounded-md bg-amber-300 px-4 py-2 font-medium text-black" onClick={() => void save()}>{id ? "Save" : "Create"}</button>{id && <button type="button" className="rounded-md border border-neutral-700 px-4 py-2" onClick={() => setHistoryOpen((value) => !value)}>Version history</button>}</div><div className="mt-4 flex items-center gap-3 text-sm"><span className={tone} role="status">{status}</span><span className="text-neutral-500">Revision {revision} · autosaves after 1.8s idle</span></div>{status === "Conflict" && <div className="mt-4 rounded border border-red-900 bg-red-950/40 p-3 text-sm text-red-200">This document changed since you opened it. Reload Latest or save a copy after reviewing.</div>}{status === "Error" && <div className="mt-4 rounded border border-red-900 bg-red-950/40 p-3 text-sm text-red-200">Unable to save. Your current editor content is preserved in memory. <button type="button" className="underline" onClick={() => void save()}>Retry</button></div>}{historyOpen && id && <VersionHistory documentId={id} organizationId={activeOrganizationId} onRestored={(data) => { setRevision(data.revision_number); editor?.commands.setContent(data.content_json ?? initial); setStatus("Saved"); }} />}<div className="mt-4 flex flex-wrap gap-2">{id && <button type="button" className="rounded border border-neutral-700 px-3 py-2 text-sm" onClick={() => { const title = window.getSelection()?.toString().trim() || "Follow up on document"; void apiRequest(`/api/documents/${id}/office-task/?organization_id=${activeOrganizationId}`, { method: "POST", body: JSON.stringify({ title, description: `Source Office document: ${id}`, priority: "normal" }) }).then(() => setStatus("Saved")).catch(() => setStatus("Error")); }}>Create Task</button>}</div>{id && <div className="mt-4 flex flex-wrap gap-2"><button type="button" className="rounded border border-neutral-700 px-3 py-2 text-sm" onClick={async () => { if (!activeOrganizationId) return; const copy = await apiRequest<OfficeResponse>(`/api/documents/${id}/office-duplicate/`, { method: "POST", body: JSON.stringify({ organization_id: activeOrganizationId }) }); router.push(`/workspace/office/${copy.document}`); }}>Duplicate</button><button type="button" className="rounded border border-neutral-700 px-3 py-2 text-sm" onClick={async () => { if (!activeOrganizationId) return; await apiRequest(`/api/documents/${id}/archive/`, { method: "POST", body: JSON.stringify({ organization: activeOrganizationId }) }); router.push("/workspace/office"); }}>Archive</button></div>}{id && format !== "sheet" && <DocumentTools editor={editor} />}{id && format !== "sheet" && <OfficeAttachments documentId={id} organizationId={activeOrganizationId} editor={editor} />}{format === "sheet" ? <SheetFallback documentId={id} organizationId={activeOrganizationId} workspaceId={activeWorkspaceId} revision={revision} onRevision={setRevision} /> : <div className="mt-6 rounded-lg border border-neutral-800 bg-neutral-950 p-4"><Toolbar editor={editor} /><EditorContent editor={editor} className="office-editor mt-4 min-h-[28rem]" /></div>}<p className="mt-4 text-sm text-neutral-500">Structured JSON is validated server-side. Offline edits are not queued or cached.</p></main></Frame>;
}

function VersionHistory({ documentId, organizationId, onRestored }: { documentId: string; organizationId: string | null; onRestored: (data: OfficeResponse) => void }) {
  const [rows, setRows] = useState<Revision[]>([]); const [preview, setPreview] = useState<Revision | null>(null);
  useEffect(() => { if (organizationId) void apiRequest<Revision[]>(`/api/documents/${documentId}/office-revisions/?organization_id=${organizationId}`).then(setRows); }, [documentId, organizationId]);
  async function restore(revision: number) { if (!organizationId) return; const data = await apiRequest<OfficeResponse>(`/api/documents/${documentId}/office-revisions/${revision}/restore/`, { method: "POST", body: JSON.stringify({ organization_id: organizationId }) }); onRestored(data); }
  return <section aria-label="Version history" className="mt-5 rounded-lg border border-neutral-800 bg-neutral-900 p-4"><h2 className="font-semibold">Version history</h2>{rows.length ? <div className="mt-3 space-y-2">{rows.map((row) => <div key={row.revision_number} className="border-t border-neutral-800 py-3"><div className="flex flex-wrap items-center justify-between gap-3"><span>Revision {row.revision_number}<span className="ml-2 text-sm text-neutral-500">{new Date(row.created_at).toLocaleString()}</span></span><div className="flex gap-2"><button type="button" className="rounded border border-neutral-700 px-3 py-1 text-sm" onClick={() => setPreview(row)}>Preview</button><button type="button" className="rounded border border-neutral-700 px-3 py-1 text-sm" onClick={() => void restore(row.revision_number)}>Restore</button></div></div>{preview?.revision_number === row.revision_number && <pre className="mt-3 max-h-48 overflow-auto rounded bg-neutral-950 p-3 text-xs text-neutral-400">Viewing Revision {row.revision_number}{"\n"}{JSON.stringify(row.content_json, null, 2)}</pre>}</div>)}</div> : <p className="mt-3 text-sm text-neutral-500">No immutable checkpoints yet.</p>}</section>;
}

// Sheet mutations require the document.manage permission; Django remains authoritative.
function SheetFallback({ documentId, organizationId, workspaceId, revision, onRevision }: { documentId?: string; organizationId: string | null; workspaceId: string | null; revision: number; onRevision: (revision: number) => void }) {
  type Column = { id: string; name: string; type: string; options?: { key: string; label: string }[] };
  type Cell = string | boolean | Record<string, string>;
  type Row = { id: string; cells: Record<string, Cell> };
  type Sheet = { type: "sheet"; columns: Column[]; rows: Row[] };
  type Filter = { id: string; operator: string; value: string };
  const types = ["TEXT", "NUMBER", "DATE", "DATETIME", "CURRENCY", "STATUS", "SELECT", "CHECKBOX", "USER", "ENTITY_LINK"];
  const [sheet, setSheet] = useState<Sheet>({ type: "sheet", columns: [{ id: "column_1", name: "Column 1", type: "TEXT" }], rows: [] });
  const [message, setMessage] = useState("Unsaved");
  const [csv, setCsv] = useState("");
  const [sort, setSort] = useState<{ id: string; direction: "asc" | "desc" } | null>(null);
  const [filter, setFilter] = useState<Filter | null>(null);
  const [confirming, setConfirming] = useState("");
  const scope = organizationId ? `organization_id=${organizationId}${workspaceId ? `&workspace_id=${workspaceId}` : ""}` : "";
  useEffect(() => {
    if (!documentId || !organizationId) return;
    void apiRequest<{ sheet: Sheet; revision_number: number }>(`/api/documents/${documentId}/office-sheet/?${scope}`).then((data) => {
      if (data.sheet.columns.length) setSheet(data.sheet);
      onRevision(data.revision_number);
      setMessage("Saved");
    }).catch(() => setMessage("Error"));
  }, [documentId, organizationId, onRevision, scope]);
  const displayRows = useMemo(() => {
    let rows = sheet.rows.slice();
    if (filter) rows = rows.filter((row) => {
      const text = String(row.cells[filter.id] ?? "");
      const target = filter.value.toLowerCase();
      if (filter.operator === "is_empty") return text === "";
      if (filter.operator === "is_not_empty") return text !== "";
      if (filter.operator === "contains") return text.toLowerCase().includes(target);
      if (filter.operator === "equals" || filter.operator === "is") return text.toLowerCase() === target;
      if (filter.operator === "not_equals" || filter.operator === "is_not") return text.toLowerCase() !== target;
      if (filter.operator === "greater") return text > filter.value;
      if (filter.operator === "less") return text < filter.value;
      return true;
    });
    if (sort) {
      const column = sheet.columns.find((item) => item.id === sort.id);
      rows.sort((left, right) => {
        const a = String(left.cells[sort.id] ?? "");
        const b = String(right.cells[sort.id] ?? "");
        const result = column?.type === "NUMBER" || column?.type === "CURRENCY"
          ? Number(a || 0) - Number(b || 0)
          : a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
        return sort.direction === "asc" ? result : -result;
      });
    }
    return rows;
  }, [filter, sheet, sort]);
  async function mutate(operation: string, payload: Record<string, unknown> = {}) {
    if (!documentId || !organizationId) return;
    setMessage("Saving");
    try {
      const data = await apiRequest<{ sheet: Sheet; revision_number: number }>(`/api/documents/${documentId}/office-sheet/?${scope}`, {
        method: "PATCH",
        body: JSON.stringify({ ...payload, operation, organization_id: organizationId, workspace_id: workspaceId, expected_revision: revision }),
      });
      setSheet(data.sheet); onRevision(data.revision_number); setMessage("Saved"); setConfirming("");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to save Sheet."); }
  }
  function update(rowId: string, columnId: string, value: string) {
    setSheet((current) => ({ ...current, rows: current.rows.map((row) => row.id === rowId ? { ...row, cells: { ...row.cells, [columnId]: value } } : row) }));
    setMessage("Unsaved");
  }
  async function save() {
    if (!documentId || !organizationId) return;
    setMessage("Saving");
    try {
      const data = await apiRequest<{ sheet: Sheet; revision_number: number }>(`/api/documents/${documentId}/office-sheet/?${scope}`, { method: "PATCH", body: JSON.stringify({ organization_id: organizationId, workspace_id: workspaceId, sheet, expected_revision: revision }) });
      setSheet(data.sheet); onRevision(data.revision_number); setMessage("Saved");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to save Sheet."); }
  }
  async function importCsv() {
    if (!documentId || !organizationId) return;
    try {
      const data = await apiRequest<{ sheet: Sheet; revision_number: number }>(`/api/documents/${documentId}/office-sheet/?${scope}`, { method: "POST", body: JSON.stringify({ organization_id: organizationId, workspace_id: workspaceId, operation: "import_csv", csv, expected_revision: revision }) });
      setSheet(data.sheet); onRevision(data.revision_number); setCsv(""); setMessage("Saved");
    } catch (error) { setMessage(error instanceof Error ? error.message : "CSV import failed."); }
  }
  function cellInput(row: Row, column: Column) {
    const value = row.cells[column.id];
    const className = "min-w-0 border-r border-neutral-900 bg-transparent p-3 outline-none focus:bg-neutral-900 focus:ring-1 focus:ring-amber-300";
    if (column.type === "CHECKBOX") {
      return <input aria-label={`${column.name} ${row.id}`} type="checkbox" className={className} checked={value === true || value === "true"} onChange={(event) => update(row.id, column.id, event.target.checked ? "true" : "false")} />;
    }
    if (["SELECT", "STATUS"].includes(column.type) && column.options?.length) {
      return <select aria-label={`${column.name} ${row.id}`} className={className} value={String(value ?? "")} onChange={(event) => update(row.id, column.id, event.target.value)}><option value="">—</option>{column.options.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}</select>;
    }
    return <input aria-label={`${column.name} ${row.id}`} className={className} value={String(value ?? "")} onChange={(event) => update(row.id, column.id, event.target.value)} />;
  }
  function removeColumn(column: Column) {
    const key = `column:${column.id}`;
    if (confirming !== key) { setConfirming(key); return; }
    void mutate("remove_column", { column_id: column.id, confirmed: true });
  }
  function removeRow(row: Row) {
    const key = `row:${row.id}`;
    if (confirming !== key) { setConfirming(key); return; }
    void mutate("delete_row", { row_id: row.id });
  }
  function configureOptions(event: React.FocusEvent<HTMLInputElement>, columnId: string) {
    const options = event.target.value.split(",").map((item) => {
      const parts = item.trim().split(":");
      return { key: parts[0], label: parts.slice(1).join(":") || parts[0] };
    }).filter((item) => item.key && item.label);
    void mutate("configure_column", { column_id: columnId, options });
  }
  return <section aria-label="Sheet grid" className="mt-6 rounded-lg border border-neutral-800 bg-neutral-950">
    <h2 className="sr-only">Column Settings</h2>
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-neutral-800 p-3">
      <span className="text-sm text-neutral-400" role="status">{message} · revision {revision} · {displayRows.length}/{sheet.rows.length} rows</span>
      <div className="flex flex-wrap gap-2"><button type="button" className="rounded border border-neutral-700 px-3 py-1 text-sm" onClick={() => void mutate("add_column", { column: { name: `Column ${sheet.columns.length + 1}`, type: "TEXT" } })}>Add Column</button><button type="button" className="rounded border border-neutral-700 px-3 py-1 text-sm" onClick={() => void mutate("add_row")}>Add Row</button><button type="button" className="rounded border border-neutral-700 px-3 py-1 text-sm" onClick={() => void mutate("insert_row", { index: 0 })}>Insert Row</button><button type="button" className="rounded border border-neutral-700 px-3 py-1 text-sm" onClick={() => void save()}>Save Sheet</button>{documentId && <a className="rounded border border-neutral-700 px-3 py-1 text-sm" href={`/api/documents/${documentId}/office-sheet/export/?${scope}`}>Export CSV</a>}</div>
    </div>
    <div className="grid gap-2 border-b border-neutral-800 p-3 sm:grid-cols-2">
      <label className="text-sm text-neutral-400">Sort<select aria-label="Sort Sheet" className="ml-2 rounded border border-neutral-700 bg-neutral-900 p-1" value={sort?.id ?? ""} onChange={(event) => setSort(event.target.value ? { id: event.target.value, direction: sort?.direction ?? "asc" } : null)}><option value="">None</option>{sheet.columns.map((column) => <option key={column.id} value={column.id}>{column.name}</option>)}</select>{sort && <button type="button" className="ml-2 underline" onClick={() => setSort({ ...sort, direction: sort.direction === "asc" ? "desc" : "asc" })}>{sort.direction === "asc" ? "Ascending" : "Descending"}</button>}</label>
      <label className="text-sm text-neutral-400">Filter<select aria-label="Filter Sheet" className="ml-2 rounded border border-neutral-700 bg-neutral-900 p-1" value={filter?.id ?? ""} onChange={(event) => setFilter(event.target.value ? { id: event.target.value, operator: "contains", value: "" } : null)}><option value="">None</option>{sheet.columns.map((column) => <option key={column.id} value={column.id}>{column.name}</option>)}</select>{filter && <><select aria-label="Filter operator" className="ml-2 rounded border border-neutral-700 bg-neutral-900 p-1" value={filter.operator} onChange={(event) => setFilter({ ...filter, operator: event.target.value })}><option value="contains">contains</option><option value="equals">equals</option><option value="not_equals">not equals</option><option value="is_empty">is empty</option><option value="is_not_empty">is not empty</option><option value="greater">greater than</option><option value="less">less than</option></select>{!['is_empty', 'is_not_empty'].includes(filter.operator) && <input aria-label="Filter value" className="ml-2 rounded border border-neutral-700 bg-neutral-900 p-1" value={filter.value} onChange={(event) => setFilter({ ...filter, value: event.target.value })} />}<button type="button" className="ml-2 underline" onClick={() => setFilter(null)}>Clear Filter</button></>}</label>
    </div>
    <div className="hidden overflow-x-auto sm:block"><div className="min-w-[48rem]">
      <div className="grid border-b border-neutral-800 bg-neutral-900 text-sm text-neutral-400" style={{ gridTemplateColumns: `repeat(${sheet.columns.length + 1}, minmax(9rem, 1fr))` }}>{sheet.columns.map((column, index) => <div key={column.id} className="p-2"><input aria-label={`${column.name} column name`} className="w-full bg-transparent font-medium" value={column.name} onChange={(event) => setSheet((current) => ({ ...current, columns: current.columns.map((item) => item.id === column.id ? { ...item, name: event.target.value } : item) }))} onBlur={() => void mutate("rename_column", { column_id: column.id, name: column.name })} /><select aria-label={`${column.name} column type`} className="mt-1 w-full bg-neutral-950 text-xs" value={column.type} onChange={(event) => void mutate("change_column_type", { column_id: column.id, type: event.target.value })}>{types.map((type) => <option key={type}>{type}</option>)}</select>{["SELECT", "STATUS"].includes(column.type) && <input aria-label={`${column.name} options`} className="mt-1 w-full bg-neutral-950 text-xs" defaultValue={(column.options ?? []).map((item) => `${item.key}:${item.label}`).join(",")} placeholder="key:label, key:label" onBlur={(event) => configureOptions(event, column.id)} />}<div className="mt-1 flex gap-1"><button type="button" aria-label={`Move ${column.name} left`} disabled={index === 0} onClick={() => void mutate("move_column", { column_id: column.id, delta: -1 })}>←</button><button type="button" aria-label={`Move ${column.name} right`} disabled={index === sheet.columns.length - 1} onClick={() => void mutate("move_column", { column_id: column.id, delta: 1 })}>→</button><button type="button" aria-label={`Remove ${column.name}`} onClick={() => removeColumn(column)}>{confirming === `column:${column.id}` ? "Confirm remove" : "Remove"}</button></div></div>)}<div className="p-2 text-xs">Rows</div></div>
      {displayRows.map((row) => <div className="grid border-b border-neutral-900" key={row.id} style={{ gridTemplateColumns: `repeat(${sheet.columns.length + 1}, minmax(9rem, 1fr))` }}>{sheet.columns.map((column) => <div key={`${row.id}-${column.id}`}>{cellInput(row, column)}</div>)}<div className="flex gap-1 p-2"><button type="button" aria-label={`Move row ${row.id} up`} onClick={() => void mutate("move_row", { row_id: row.id, delta: -1 })}>↑</button><button type="button" aria-label={`Move row ${row.id} down`} onClick={() => void mutate("move_row", { row_id: row.id, delta: 1 })}>↓</button><button type="button" onClick={() => void mutate("duplicate_row", { row_id: row.id })}>Duplicate</button><button type="button" onClick={() => removeRow(row)}>{confirming === `row:${row.id}` ? "Confirm delete" : "Delete"}</button></div></div>)}
    </div></div>
    <div className="space-y-3 p-3 sm:hidden">{displayRows.map((row) => <article className="rounded border border-neutral-800 p-3" key={row.id}><div className="mb-2 flex justify-between text-sm text-neutral-400"><span>{row.id}</span><span className="flex gap-2"><button type="button" onClick={() => void mutate("duplicate_row", { row_id: row.id })}>Duplicate</button><button type="button" onClick={() => removeRow(row)}>{confirming === `row:${row.id}` ? "Confirm delete" : "Delete"}</button></span></div>{sheet.columns.map((column) => <label className="mb-2 block text-sm" key={`${row.id}-mobile-${column.id}`}>{column.name}{cellInput(row, column)}</label>)}</article>)}</div>
    <div className="border-t border-neutral-800 p-3"><label className="block text-sm text-neutral-400">Import CSV<textarea aria-label="CSV import" className="mt-2 min-h-20 w-full rounded border border-neutral-700 bg-neutral-900 p-2" value={csv} onChange={(event) => setCsv(event.target.value)} placeholder="Paste CSV for preview/import" /></label><button type="button" className="mt-2 rounded border border-neutral-700 px-3 py-1 text-sm" disabled={!csv.trim()} onClick={() => void importCsv()}>Import CSV</button></div>
  </section>;
}
