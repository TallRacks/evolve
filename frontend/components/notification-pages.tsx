"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { RouteGuard } from "@/components/auth/route-guard";
import { apiRequest } from "@/lib/api/client";
import {
  buttonClass,
  fieldClass,
  PageHeader,
  secondaryButtonClass,
  StatusBadge,
} from "@/components/ui/page";

type PlatformItem = { id:string; notification_type:string; organization:string|null; recipient_count:number; priority:string };
type Item = { id:string; notification_type:string; category:string; title:string; message:string; priority:string; action_url:string; organization:string|null; created_at:string; read_at:string|null; email_status:string|null };
type Page<T> = { count:number; results:T[] };
type Preference = { category:string; label:string; description:string; in_app_enabled:boolean; email_enabled:boolean; in_app_disableable:boolean; email_disableable:boolean };
type Delivery = { id:string; organization_name:string|null; connector_name:string|null; category:string; template_key:string; recipient_email_snapshot:string; subject_snapshot:string; status:string; failure_message:string; attempt_number:number; attempted_at:string };
const cats = ["team","bookings","call_sheets","contracts","production","music","marketing","documents","finance","rights","security","system"];

export function NotificationsPage() {
  const router=useRouter(); const [data,setData]=useState<Item[]>([]); const [unread,setUnread]=useState(false); const [category,setCategory]=useState(""); const [priority,setPriority]=useState("");
  const load=useCallback(()=>{const p=new URLSearchParams();if(unread)p.set("unread","true");if(category)p.set("category",category);if(priority)p.set("priority",priority);return apiRequest<Page<Item>>("/api/notifications/?"+p).then(x=>setData(x.results))},[unread,category,priority]);
  useEffect(()=>{void load()},[load]);
  async function read(item:Item,value=true){await apiRequest(`/api/notifications/${item.id}/read/`,{method:"POST",body:JSON.stringify({read:value})});if(value&&item.action_url)router.push(item.action_url);else await load()}
  return <RouteGuard portal="dashboard"><AppShell><PageHeader eyebrow="Activity" title="Notifications" actions={<button className={secondaryButtonClass} onClick={async()=>{await apiRequest("/api/notifications/read-all/",{method:"POST"});await load()}}>Mark all read</button>}/>
    <div className="mt-6 grid gap-3 sm:grid-cols-3"><label className="flex items-center gap-2"><input checked={unread} onChange={e=>setUnread(e.target.checked)} type="checkbox"/>Unread only</label><select className={fieldClass} value={category} onChange={e=>setCategory(e.target.value)}><option value="">All categories</option>{cats.map(x=><option key={x}>{x}</option>)}</select><select className={fieldClass} value={priority} onChange={e=>setPriority(e.target.value)}><option value="">All priorities</option>{["low","normal","high","urgent"].map(x=><option key={x}>{x}</option>)}</select></div>
    <div className="mt-7 grid gap-3">{data.map(item=><article className={`rounded-md border p-5 ${item.read_at?"border-neutral-800 bg-neutral-900":"border-amber-700 bg-neutral-900"}`} key={item.id}><div className="flex flex-wrap justify-between gap-3"><div><p className="text-xs text-neutral-500">{item.organization||"Platform"} / {item.category}</p><h2 className="mt-1 font-semibold">{item.title}</h2><p className="mt-2 text-sm text-neutral-300">{item.message}</p><p className="mt-2 text-xs text-neutral-500">{new Date(item.created_at).toLocaleString()}{item.email_status?` / Email: ${item.email_status.replaceAll("_"," ")}`:""}</p></div><StatusBadge positive={!item.read_at}>{item.priority}</StatusBadge></div><div className="mt-4 flex gap-2">{item.action_url&&<button className={buttonClass} onClick={()=>void read(item)}>Open</button>}<button className={secondaryButtonClass} onClick={()=>void read(item,!item.read_at)}>{item.read_at?"Mark unread":"Mark read"}</button><button className={secondaryButtonClass} onClick={async()=>{await apiRequest(`/api/notifications/${item.id}/archive/`,{method:"POST"});await load()}}>Archive</button></div></article>)}{!data.length&&<p className="py-12 text-center text-neutral-500">No notifications</p>}</div>
  </AppShell></RouteGuard>
}

export function NotificationPreferencesPage() {
  const [data,setData]=useState<Preference[]>([]); const [saved,setSaved]=useState(""); const [saving,setSaving]=useState(false);
  const load=useCallback(()=>apiRequest<Preference[]>("/api/notification-preferences/").then(setData),[]); useEffect(()=>{void load()},[load]);
  function toggle(category:string,key:"in_app_enabled"|"email_enabled",value:boolean){setData(current=>current.map(x=>x.category===category?{...x,[key]:value}:x))}
  async function save(){setSaving(true);setSaved("");try{setData(await apiRequest<Preference[]>("/api/notification-preferences/",{method:"PATCH",body:JSON.stringify(data.map(({category,in_app_enabled,email_enabled})=>({category,in_app_enabled,email_enabled})))}));setSaved("Preferences saved.")}finally{setSaving(false)}}
  async function reset(){setData(await apiRequest<Preference[]>("/api/notification-preferences/reset/",{method:"POST"}));setSaved("Defaults restored.")}
  return <RouteGuard portal="dashboard"><AppShell><PageHeader eyebrow="Profile" title="Notification preferences" description="Choose how operational updates reach you." actions={<div className="flex gap-2"><button className={secondaryButtonClass} onClick={()=>void reset()}>Reset</button><button className={buttonClass} disabled={saving} onClick={()=>void save()}>{saving?"Saving...":"Save"}</button></div>}/>{saved&&<p aria-live="polite" className="mt-4 text-sm text-amber-300">{saved}</p>}
    <div className="mt-7 max-w-4xl overflow-hidden rounded-md border border-neutral-800"><div className="grid grid-cols-[1fr_5rem_5rem] gap-3 bg-neutral-900 px-5 py-3 text-xs uppercase text-neutral-500"><span>Category</span><span className="text-center">In app</span><span className="text-center">Email</span></div>{data.map(x=><div className="grid grid-cols-[1fr_5rem_5rem] items-center gap-3 border-t border-neutral-800 p-5" key={x.category}><div><p className="font-medium">{x.label}</p><p className="mt-1 text-sm text-neutral-500">{x.description}</p></div><input aria-label={`${x.label} in-app`} className="mx-auto" checked={x.in_app_enabled} disabled={!x.in_app_disableable} onChange={e=>toggle(x.category,"in_app_enabled",e.target.checked)} type="checkbox"/><input aria-label={`${x.label} email`} className="mx-auto" checked={x.email_enabled} disabled={!x.email_disableable} onChange={e=>toggle(x.category,"email_enabled",e.target.checked)} type="checkbox"/></div>)}</div>
  </AppShell></RouteGuard>
}

export function PlatformNotificationsPage(){const[data,setData]=useState<PlatformItem[]>([]);useEffect(()=>{void apiRequest<PlatformItem[]>("/api/platform/notifications/").then(setData)},[]);return <RouteGuard portal="platform"><AppShell><PageHeader eyebrow="Platform" title="Notification oversight" description="Aggregate delivery metadata without recipient inbox impersonation."/><div className="mt-7 grid gap-3">{data.map(x=><div className="grid gap-2 rounded-md border border-neutral-800 p-4 sm:grid-cols-4" key={x.id}><span>{x.notification_type}</span><span>{x.organization||"Platform"}</span><span>{x.recipient_count} recipients</span><span>{x.priority}</span></div>)}</div></AppShell></RouteGuard>}

export function PlatformEmailDeliveryPage(){
  const [data,setData]=useState<Delivery[]>([]); const [status,setStatus]=useState(""); const [message,setMessage]=useState("");
  const load=useCallback(()=>apiRequest<Page<Delivery>>(`/api/platform/email-deliveries/${status?`?status=${status}`:""}`).then(x=>setData(x.results)),[status]);useEffect(()=>{void load()},[load]);
  async function retry(item:Delivery){setMessage("");try{await apiRequest(`/api/platform/email-deliveries/${item.id}/retry/`,{method:"POST"});setMessage("Delivery retried.");await load()}catch(caught){setMessage(caught instanceof Error?caught.message:"Retry failed.")}}
  return <RouteGuard portal="platform"><AppShell><PageHeader eyebrow="Platform" title="Email delivery" description="Transactional delivery attempts. Sent means accepted by the configured SMTP server."/><div className="mt-6 max-w-xs"><select className={fieldClass} value={status} onChange={e=>setStatus(e.target.value)}><option value="">All statuses</option>{["pending","sent","failed","not_configured","skipped","suppressed"].map(x=><option key={x}>{x.replaceAll("_"," ")}</option>)}</select></div>{message&&<p aria-live="polite" className="mt-4 text-sm text-amber-300">{message}</p>}<div className="mt-7 overflow-x-auto"><table className="min-w-full text-left text-sm"><thead className="text-neutral-500"><tr><th className="p-3">Attempt</th><th className="p-3">Recipient</th><th className="p-3">Message</th><th className="p-3">Status</th><th className="p-3">Time</th><th className="p-3"></th></tr></thead><tbody>{data.map(x=><tr className="border-t border-neutral-800" key={x.id}><td className="p-3">{x.attempt_number}</td><td className="p-3">{x.recipient_email_snapshot}<span className="block text-xs text-neutral-500">{x.organization_name||"Platform"}</span></td><td className="p-3">{x.subject_snapshot}<span className="block text-xs text-neutral-500">{x.template_key}</span></td><td className="p-3"><StatusBadge positive={x.status==="sent"}>{x.status.replaceAll("_"," ")}</StatusBadge>{x.failure_message&&<span className="mt-1 block text-xs text-neutral-500">{x.failure_message}</span>}</td><td className="p-3 whitespace-nowrap">{new Date(x.attempted_at).toLocaleString()}</td><td className="p-3">{["failed","not_configured"].includes(x.status)&&<button className={secondaryButtonClass} onClick={()=>void retry(x)}>Retry</button>}</td></tr>)}</tbody></table>{!data.length&&<p className="py-12 text-center text-neutral-500">No application emails have been attempted yet.</p>}</div></AppShell></RouteGuard>
}
