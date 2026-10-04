"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth/auth-provider";
import { RouteGuard } from "@/components/auth/route-guard";
import { apiRequest } from "@/lib/api/client";
import { EmptyState, fieldClass, PageHeader, secondaryButtonClass } from "@/components/ui/page";

type DriveFile = { id: string; name: string; mimeType: string; modifiedTime?: string; size?: string; webViewLink?: string; iconLink?: string };
type DrivePage = { files?: DriveFile[]; nextPageToken?: string };

export function GoogleDrivePage() {
  const { activeOrganizationId } = useAuth();
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [query, setQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [pageToken, setPageToken] = useState("");
  const [nextPageToken, setNextPageToken] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load(token = "", replace = true, search = activeQuery) {
    if (!activeOrganizationId) return;
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ organization_id: activeOrganizationId, page_size: "50" });
      if (search) params.set("q", search);
      if (token) params.set("page_token", token);
      const data = await apiRequest<DrivePage>("/api/google-drive/files/?" + params.toString());
      setFiles((current) => replace ? (data.files || []) : [...current, ...(data.files || [])]);
      setPageToken(token);
      setNextPageToken(data.nextPageToken || "");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Google Drive could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { queueMicrotask(() => void load("", true, "")); }, [activeOrganizationId]);

  function search() {
    setActiveQuery(query.trim());
    void load("", true, query.trim());
  }

  return <RouteGuard portal="workspace"><AppShell organizationScoped>
    <PageHeader eyebrow="Workspace / Google Drive" title="Google Drive" description="Browse and download the connected Drive workspace without exposing OAuth credentials." />
    <div className="mt-6 flex flex-wrap gap-3"><input className={fieldClass} placeholder="Search Drive files" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") search(); }} /><button className={secondaryButtonClass} onClick={search}>Search</button>{activeQuery && <button className={secondaryButtonClass} onClick={() => { setQuery(""); setActiveQuery(""); void load("", true, ""); }}>Clear</button>}</div>
    {error && <p className="mt-4 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    <div className="mt-7 grid gap-3">{loading && !files.length ? <p className="text-sm text-[var(--text-muted)]">Loading Drive files...</p> : files.length ? files.map((file) => <div className="evolve-panel flex flex-wrap items-center justify-between gap-3 p-4" key={file.id}><div><p className="font-medium text-[var(--text-primary)]">{file.name}</p><p className="mt-1 text-xs text-[var(--text-muted)]">{file.mimeType} · {file.modifiedTime ? new Date(file.modifiedTime).toLocaleString() : ""}</p></div><div className="flex gap-2">{file.webViewLink && <a className={secondaryButtonClass} href={file.webViewLink} target="_blank" rel="noreferrer">Open</a>}<a className={secondaryButtonClass} href={"/api/google-drive/files/" + encodeURIComponent(file.id) + "/download/?organization_id=" + activeOrganizationId + "&mime_type=" + encodeURIComponent(file.mimeType)}>Download</a></div></div>) : <EmptyState title="No Drive files" detail="Connect Google Drive in Platform settings or adjust your search." />}</div>
    <div className="mt-5 flex flex-wrap items-center justify-between gap-3 text-sm text-[var(--text-muted)]"><span>{files.length} files loaded</span>{nextPageToken && <button className={secondaryButtonClass} disabled={loading} onClick={() => void load(nextPageToken, false)}>Load more</button>}{pageToken && <button className={secondaryButtonClass} disabled={loading} onClick={() => { setFiles([]); void load("", true); }}>Back to first page</button>}</div>
  </AppShell></RouteGuard>;
}
