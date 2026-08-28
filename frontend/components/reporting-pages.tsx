"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { RouteGuard } from "@/components/auth/route-guard";
import { useAuth } from "@/components/auth/auth-provider";
import { confirmAction } from "@/components/ui/action-dialog";
import { buttonClass, EmptyState, fieldClass, PageHeader, secondaryButtonClass, StatCard } from "@/components/ui/page";
import { apiRequest } from "@/lib/api/client";

const reports = [
  ["bookings", "Booking Pipeline"], ["artists", "Artist Activity"],
  ["promoters", "Promoters"], ["venues", "Venues"],
  ["production", "Production Attention"], ["travel", "Travel"],
  ["tasks", "Tasks / Workload"], ["finance", "Finance"],
  ["contracts", "Contracts"], ["music", "Music / Releases"],
  ["campaigns", "Campaigns / Rollouts"], ["rights", "Rights Completeness"],
  ["royalties", "Royalty Statement Operations"],
] as const;

interface Report { report_key:string; title:string; summary:{total:number;by_status?:Record<string,number>;currencies?:Record<string,unknown>}; rows:Record<string,unknown>[] }
interface SavedView { id:string;report_key:string;name:string;filters:Record<string,string>;sort:string;is_default:boolean }

export function ReportsPage() {
  const { activeOrganizationId } = useAuth();
  const [reportKey, setReportKey] = useState("bookings");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [data, setData] = useState<Report|null>(null);
  const [saved, setSaved] = useState<SavedView[]>([]);
  const [message, setMessage] = useState("");
  const query = useMemo(() => {
    const params = new URLSearchParams({organization_id:activeOrganizationId??"",report_key:reportKey});
    if(status)params.set("status",status);if(priority)params.set("priority",priority);
    return params.toString();
  },[activeOrganizationId,priority,reportKey,status]);
  const loadSaved = useCallback(async () => {
    if(activeOrganizationId)setSaved(await apiRequest<SavedView[]>(`/api/reports/saved-views/?organization_id=${activeOrganizationId}`));
  },[activeOrganizationId]);
  useEffect(() => {
    if (!activeOrganizationId) return;
    let cancelled = false;
    apiRequest<Report>(`/api/reports/?${query}`).then((next) => { if (!cancelled) { setData(next); setMessage(""); } }).catch((caught) => { if (!cancelled) { setData(null); setMessage(caught instanceof Error ? caught.message : "Unable to load report."); } });
    return () => { cancelled = true; };
  }, [activeOrganizationId, query]);
  useEffect(() => {
    if (!activeOrganizationId) return;
    let cancelled = false;
    apiRequest<SavedView[]>(`/api/reports/saved-views/?organization_id=${activeOrganizationId}`).then((next) => { if (!cancelled) setSaved(next); });
    return () => { cancelled = true; };
  }, [activeOrganizationId]);
  async function saveView(event:FormEvent<HTMLFormElement>){event.preventDefault();if(!activeOrganizationId)return;const element=event.currentTarget;const form=new FormData(element);await apiRequest("/api/reports/saved-views/",{method:"POST",body:JSON.stringify({organization_id:activeOrganizationId,report_key:reportKey,name:form.get("name"),filters:{status,priority},is_default:form.get("is_default")==="on"})});element.reset();await loadSaved();setMessage("View saved.")}
  async function updateView(item:SavedView){const name=window.prompt("Saved view name",item.name);if(!name)return;await apiRequest(`/api/reports/saved-views/${item.id}/`,{method:"PATCH",body:JSON.stringify({name,filters:{status,priority},is_default:item.is_default})});await loadSaved()}
  async function removeView(item:SavedView){if(!await confirmAction(`Delete saved view ${item.name}?`))return;await apiRequest(`/api/reports/saved-views/${item.id}/`,{method:"DELETE"});await loadSaved()}
  function applyView(item:SavedView){setReportKey(item.report_key);setStatus(item.filters.status??"");setPriority(item.filters.priority??"")}
  return <RouteGuard portal="workspace"><AppShell organizationScoped><PageHeader eyebrow="Insights" title="Reports" description="Permission-aware operational reporting from current source records." actions={data?<a className={buttonClass} href={`/api/reports/export/?${query}`}>Export CSV</a>:undefined}/><div className="mt-6 grid gap-3 sm:grid-cols-3"><label className="text-sm">Report<select className={`mt-1 ${fieldClass}`} value={reportKey} onChange={e=>setReportKey(e.target.value)}>{reports.map(([key,label])=><option value={key} key={key}>{label}</option>)}</select></label><label className="text-sm">Status<input className={`mt-1 ${fieldClass}`} value={status} onChange={e=>setStatus(e.target.value)} placeholder="All statuses"/></label><label className="text-sm">Priority<input className={`mt-1 ${fieldClass}`} value={priority} onChange={e=>setPriority(e.target.value)} placeholder="All priorities"/></label></div>{message&&<p aria-live="polite" className="mt-4 text-sm text-amber-300">{message}</p>}{data&&<><div className="mt-6 grid gap-4 sm:grid-cols-3"><StatCard label="Records" value={data.summary.total}/>{Object.entries(data.summary.by_status??{}).slice(0,2).map(([key,value])=><StatCard label={key.replaceAll("_"," ")} value={value} key={key}/>)}</div>{data.summary.currencies&&<pre className="mt-5 overflow-auto rounded-md border border-neutral-800 bg-neutral-900 p-4 text-xs">{JSON.stringify(data.summary.currencies,null,2)}</pre>}<div className="mt-6 overflow-x-auto rounded-md border border-neutral-800">{data.rows.length===0?<EmptyState title="No report rows" detail="No records match these filters."/>:<table className="min-w-full text-left text-sm"><thead className="bg-neutral-900"><tr>{Object.keys(data.rows[0]).map(key=><th className="px-4 py-3" key={key}>{key.replaceAll("_"," ")}</th>)}</tr></thead><tbody>{data.rows.map((row,index)=><tr className="border-t border-neutral-800" key={index}>{Object.values(row).map((value,i)=><td className="whitespace-nowrap px-4 py-3" key={i}>{String(value)}</td>)}</tr>)}</tbody></table>}</div></>}<section className="mt-8 border-t border-neutral-800 pt-6"><h2 className="font-semibold">Saved views</h2><form className="mt-3 flex flex-wrap gap-3" onSubmit={saveView}><input required name="name" aria-label="Saved view name" className={`max-w-xs ${fieldClass}`} placeholder="View name"/><label className="flex items-center gap-2 text-sm"><input type="checkbox" name="is_default"/>Default</label><button className={secondaryButtonClass}>Save view</button></form><div className="mt-4 grid gap-2">{saved.map(item=><div className="flex flex-wrap items-center justify-between gap-3 border-t border-neutral-800 pt-3" key={item.id}><button className="text-left" onClick={()=>applyView(item)}>{item.name} <span className="text-neutral-500">/ {item.report_key}{item.is_default?" / default":""}</span></button><div className="flex gap-2"><button className={secondaryButtonClass} onClick={()=>void updateView(item)}>Rename / update</button><button className={secondaryButtonClass} onClick={()=>void removeView(item)}>Delete</button></div></div>)}</div></section></AppShell></RouteGuard>
}
