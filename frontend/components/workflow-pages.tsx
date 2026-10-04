"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { confirmAction } from "@/components/ui/action-dialog";
import { RouteGuard } from "@/components/auth/route-guard";
import { useAuth } from "@/components/auth/auth-provider";
import { apiRequest } from "@/lib/api/client";
import { hasOrganizationPermission } from "@/lib/auth/access";
import { buttonClass, EmptyState, fieldClass, PageHeader, secondaryButtonClass, StatusBadge } from "@/components/ui/page";

type Member = { id: string; user: { email: string; first_name: string; last_name: string } };
type Checklist = { id: string; title: string; sequence: number; is_completed: boolean };
type Task = { id: string; organization_id: string; title: string; description: string; status: string; priority: string; assigned_membership_id: string | null; assignee: { id: string; name: string } | null; assignees: { id: string; name: string }[]; due_at: string | null; sequence: number; is_overdue: boolean; context: { type: string; id: string; name: string } | null; progress: { complete: number; total: number; percent: number }; checklist_items: Checklist[]; activity?: Activity[] };
type Activity = { id: string; actor: string; action: string; description: string; destination?: string | null; created_at: string };
type TemplateSection = { id: string; key: string; title: string; body: string; sequence: number; is_enabled: boolean };
type Template = { id: string; organization: string | null; name: string; branding: { logo_url?: string; header_text?: string; footer_text?: string; primary_color?: string; accent_color?: string }; category?: string; key: string; document_type: string; description: string; status: string; is_default: boolean; version: number; sections: TemplateSection[]; variables: string[] };

const panel = "evolve-panel p-5";
const priorities = ["low", "normal", "high", "urgent"];

function Shell({ children }: { children: React.ReactNode }) {
  return <RouteGuard portal="workspace"><AppShell organizationScoped>{children}</AppShell></RouteGuard>;
}

function Progress({ value }: { value: Task["progress"] }) {
  return <div aria-label={`${value.complete} of ${value.total} complete`}><p className="text-xs text-[var(--text-secondary)]">{value.complete} / {value.total} complete</p><div className="mt-2 h-2 overflow-hidden rounded-full bg-neutral-800"><div className="h-full bg-emerald-500" style={{ width: `${value.percent}%` }}/></div></div>;
}

export function TasksPage() {
  const { activeOrganizationId, activeWorkspaceId, session } = useAuth();
  const canManage = hasOrganizationPermission(session, activeOrganizationId, "task.manage");
  const [items, setItems] = useState<Task[]>([]);
  const [view, setView] = useState("mine");
  const [query, setQuery] = useState("");
  const load = useCallback(() => activeOrganizationId ? apiRequest<Task[]>(`/api/tasks/?organization_id=${activeOrganizationId}${activeWorkspaceId ? `&workspace_id=${activeWorkspaceId}` : ""}${view === "mine" ? "&mine=true" : view ? `&status=${view}` : ""}`).then(setItems) : Promise.resolve(), [activeOrganizationId, activeWorkspaceId, view]);
  useEffect(() => { void load(); }, [load]);
  const visible = items.filter((item) => !query || `${item.title} ${item.description} ${item.assignee?.name || ""} ${item.context?.name || ""}`.toLowerCase().includes(query.toLowerCase()));
  const open = items.filter((item) => !["done", "cancelled"].includes(item.status)).length;
  const overdue = items.filter((item) => item.is_overdue).length;
  return <Shell><PageHeader eyebrow="Workflow suite" title="Tasks" description="Plan, assign, schedule, and complete operational work. Due dates flow into Calendar so the team can see the work alongside live events." actions={canManage ? <Link className={buttonClass} href="/workspace/tasks/new">New Task</Link> : undefined}/><div className="mt-7 grid gap-4 sm:grid-cols-3"><div className={panel}><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Open in view</p><p className="mt-2 text-3xl font-semibold">{open}</p></div><div className={panel}><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Overdue</p><p className="mt-2 text-3xl font-semibold text-red-600">{overdue}</p></div><Link className={`${panel} transition hover:border-[var(--accent)]`} href="/workspace/calendar"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Schedule view</p><p className="mt-2 font-semibold text-[var(--accent-strong)]">Open Calendar</p><p className="mt-1 text-sm text-[var(--text-muted)]">See task due dates with events</p></Link></div><div className="mt-7 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"><div className="flex flex-wrap gap-2" role="group" aria-label="Task views">{[["mine","My Tasks"],["","All"],["todo","Open"],["blocked","Blocked"],["done","Completed"]].map(([value,label])=><button className={view===value?buttonClass:secondaryButtonClass} key={label} onClick={()=>setView(value)}>{label}</button>)}</div><input aria-label="Search tasks" className={`${fieldClass} max-w-sm`} onChange={(event)=>setQuery(event.target.value)} placeholder="Search tasks, people, or context" value={query}/></div><div className="mt-6 grid gap-3">{visible.map(item=><article className={`${panel} evolve-panel-hover`} key={item.id}><div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0"><Link className="font-semibold text-[var(--text-primary)] hover:text-[var(--accent-strong)]" href={`/workspace/tasks/${item.id}`}>{item.title}</Link><p className="mt-1 text-sm text-[var(--text-muted)]">{item.context?.name || "General task"} · {item.assignee?.name || "Unassigned"}</p><p className={item.is_overdue?"mt-2 text-sm font-medium text-red-600":"mt-2 text-sm text-[var(--text-secondary)]"}>{item.due_at ? new Date(item.due_at).toLocaleString() : "No calendar date"}{item.is_overdue ? " · overdue" : ""}</p></div><div className="flex gap-2"><StatusBadge positive={item.status==="done"}>{item.status.replaceAll("_"," ")}</StatusBadge><StatusBadge>{item.priority}</StatusBadge></div></div><div className="mt-4 max-w-xl"><Progress value={item.progress}/></div></article>)}{!visible.length&&<EmptyState title="No tasks in this view" detail="Create a task or adjust the current view and search."/>}</div></Shell>;
}

export function TaskFormPage({ id }: { id?: string }) {
  const router = useRouter();
  const { activeOrganizationId } = useAuth();
  const [members, setMembers] = useState<Member[]>([]);
  const [task, setTask] = useState<Task | null>(null);
  const [error, setError] = useState("");
  const [contextType, setContextType] = useState("");
  const [contextOptions, setContextOptions] = useState<Record<string, { id: string; label: string }[]>>({});

  useEffect(() => {
    if (!activeOrganizationId) return;
    void apiRequest<Member[]>("/api/organizations/" + activeOrganizationId + "/members/").then(setMembers);
    void Promise.all([
      apiRequest<{ id: string; stage_name: string }[]>("/api/artists/?organization_id=" + activeOrganizationId),
      apiRequest<{ id: string; title: string; reference: string }[]>("/api/bookings/?organization_id=" + activeOrganizationId),
      apiRequest<{ id: string; title: string; artist: string }[]>("/api/music/releases/?organization_id=" + activeOrganizationId),
      apiRequest<{ id: string; name: string; brand_name?: string }[]>("/api/campaigns/?organization_id=" + activeOrganizationId),
    ]).then(([artists, bookings, releases, campaigns]) => {
      setContextOptions({
        artist: artists.map((item) => ({ id: item.id, label: item.stage_name })),
        booking: bookings.map((item) => ({ id: item.id, label: item.reference + " · " + item.title })),
        release: releases.map((item) => ({ id: item.id, label: item.title + (item.artist ? " · " + item.artist : "") })),
        campaign: campaigns.map((item) => ({ id: item.id, label: item.brand_name ? item.name + " · " + item.brand_name : item.name })),
      });
    }).catch(() => setError("Some linked-record options could not be loaded."));
    if (id) {
      void apiRequest<Task>("/api/tasks/" + id + "/").then((loaded) => {
        setTask(loaded);
        setContextType(loaded.context?.type ?? "");
      }).catch((caught) => setError(caught instanceof Error ? caught.message : "Unable to load task."));
    }
  }, [activeOrganizationId, id]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeOrganizationId) return;
    const form = new FormData(event.currentTarget);
    const selectedContext = String(form.get("context_id") || "").trim();
    const body = {
      organization_id: activeOrganizationId,
      title: form.get("title"),
      description: form.get("description"),
      assigned_membership_id: form.get("assigned_membership_id") || null,
      assignee_ids: form.getAll("assignee_ids"),
      priority: form.get("priority"),
      due_at: form.get("due_at") || null,
      sequence: Number(form.get("sequence") || 1),
      ...(contextType && selectedContext ? { [contextType]: selectedContext } : {}),
    };
    try {
      const saved = await apiRequest<Task>(id ? "/api/tasks/" + id + "/" : "/api/tasks/", {
        method: id ? "PATCH" : "POST",
        body: JSON.stringify(body),
      });
      router.push("/workspace/tasks/" + saved.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save task.");
    }
  }

  const contextLabels: Record<string, string> = { artist: "Artist", booking: "Booking", release: "Release", campaign: "Campaign" };
  const options = contextOptions[contextType] ?? [];

  return <Shell>
    <PageHeader eyebrow="Workflow suite" title={id ? "Edit Task" : "New Task"} description="Capture the outcome, owner, priority, deadline, and business context. Due work flows into Calendar." />
    <div className="mt-6 rounded-2xl border border-[var(--border)] bg-[var(--surface-raised)] p-4 text-sm text-[var(--text-secondary)]">Link each task to the booking, release, campaign, or artist it helps complete. You no longer need to copy a UUID.</div>
    {error && <p className="mt-5 text-sm text-red-600" role="alert">{error}</p>}
    <form className="mt-7 grid max-w-4xl gap-6" key={task?.id || "new"} onSubmit={submit}>
      <section className={panel}><h2 className="font-semibold">Task brief</h2><div className="mt-4 grid gap-4"><label className="text-sm text-[var(--text-secondary)]">Title<input className={"mt-2 " + fieldClass} defaultValue={task?.title} name="title" placeholder="e.g. Confirm venue production advance" required /></label><label className="text-sm text-[var(--text-secondary)]">Description<textarea className={"mt-2 min-h-36 w-full " + fieldClass + " py-3"} defaultValue={task?.description} name="description" placeholder="What needs to happen and what does done look like?" /></label></div></section>
      <section className={panel}><h2 className="font-semibold">Ownership and timing</h2><div className="mt-4 grid gap-4 sm:grid-cols-2"><label className="text-sm text-[var(--text-secondary)]">Primary assignee<select className={"mt-2 " + fieldClass} defaultValue={task?.assigned_membership_id || ""} name="assigned_membership_id"><option value="">Unassigned</option>{members.map((member) => <option key={member.id} value={member.id}>{[member.user.first_name, member.user.last_name].filter(Boolean).join(" ") || member.user.email}</option>)}</select></label><label className="text-sm text-[var(--text-secondary)]">Additional team members<select className={"mt-2 min-h-28 " + fieldClass} defaultValue={task?.assignees?.map((person) => person.id) || []} multiple name="assignee_ids">{members.map((member) => <option key={member.id} value={member.id}>{[member.user.first_name, member.user.last_name].filter(Boolean).join(" ") || member.user.email}</option>)}</select><span className="mt-1 block text-xs text-[var(--text-muted)]">Hold Ctrl/Cmd to select multiple.</span></label><label className="text-sm text-[var(--text-secondary)]">Priority<select className={"mt-2 " + fieldClass} defaultValue={task?.priority || "normal"} name="priority">{priorities.map((value) => <option key={value}>{value}</option>)}</select></label><label className="text-sm text-[var(--text-secondary)]">Due date and time<input className={"mt-2 " + fieldClass} defaultValue={task?.due_at?.slice(0, 16) || ""} name="due_at" type="datetime-local" /></label><label className="text-sm text-[var(--text-secondary)]">Queue position<input className={"mt-2 " + fieldClass} defaultValue={task?.sequence || 1} min="1" name="sequence" type="number" /></label></div></section>
      <section className={panel}><h2 className="font-semibold">Linked work</h2><p className="mt-1 text-sm text-[var(--text-muted)]">Every operational task must support one critical record. Choose exactly one record type and record before saving.</p><div className="mt-4 grid gap-4 sm:grid-cols-2"><label className="text-sm text-[var(--text-secondary)]">Critical record type <select className={"mt-2 " + fieldClass} value={contextType} onChange={(event) => setContextType(event.target.value)} name="context_type" required><option value="">Select record type</option>{Object.entries(contextLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="text-sm text-[var(--text-secondary)]">{contextType ? contextLabels[contextType] : "Record"}<select className={"mt-2 " + fieldClass} defaultValue={task?.context?.id || ""} name="context_id" disabled={!contextType} required={Boolean(contextType)}><option value="">{contextType ? "Select " + contextLabels[contextType].toLowerCase() : "Choose a record type first"}</option>{options.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label></div><p className="mt-2 text-xs text-[var(--text-muted)]">Production, travel, contract, and rollout links can still be added from their respective workspaces.</p></section>
      <div className="flex flex-wrap gap-3"><button className={buttonClass}>{id ? "Save task" : "Create task"}</button><Link className={secondaryButtonClass} href={id ? "/workspace/tasks/" + id : "/workspace/tasks"}>Cancel</Link><Link className={secondaryButtonClass} href="/workspace/calendar">Open Calendar</Link></div>
    </form>
  </Shell>;
}

export function TaskDetailPage({ id }: { id: string }) {
  const { session } = useAuth();
  const [task,setTask]=useState<Task|null>(null);const [error,setError]=useState("");
  const load=useCallback(()=>apiRequest<Task>(`/api/tasks/${id}/`).then(setTask).catch(e=>setError(e instanceof Error?e.message:"Unable to load task.")),[id]);useEffect(()=>{void load()},[load]);
  async function transition(status:string){await apiRequest(`/api/tasks/${id}/status/`,{method:"POST",body:JSON.stringify({status})});await load()}
  async function add(event:FormEvent<HTMLFormElement>){event.preventDefault();const element=event.currentTarget;const form=new FormData(element);await apiRequest(`/api/tasks/${id}/checklist/`,{method:"POST",body:JSON.stringify({title:form.get("title")})});element.reset();await load()}
  async function check(item:Checklist){await apiRequest(`/api/tasks/${id}/checklist/${item.id}/`,{method:"PATCH",body:JSON.stringify({is_completed:!item.is_completed})});await load()}
  async function updateChecklist(event:FormEvent<HTMLFormElement>,item:Checklist){event.preventDefault();const form=new FormData(event.currentTarget);await apiRequest(`/api/tasks/${id}/checklist/${item.id}/`,{method:"PATCH",body:JSON.stringify({title:form.get("title"),sequence:form.get("sequence")})});await load()}
  async function removeChecklist(item:Checklist){if(!await confirmAction("Remove this checklist item?","Remove"))return;await apiRequest(`/api/tasks/${id}/checklist/${item.id}/`,{method:"DELETE"});await load()}
  if(!task)return <Shell><p className="py-12 text-[var(--text-muted)]">{error||"Loading task..."}</p></Shell>;
  const actions=task.status==="done"?["todo"]:task.status==="blocked"?["in_progress","done","cancelled"]:["in_progress","blocked","done","cancelled"];
  const canManage=hasOrganizationPermission(session,task.organization_id,"task.manage");
  return <Shell><PageHeader eyebrow="Task" title={task.title} description={`${task.assignee?.name||"Unassigned"} / ${task.due_at?new Date(task.due_at).toLocaleString():"No due date"}`} actions={canManage?<div className="flex flex-wrap gap-2"><Link className={secondaryButtonClass} href={`/workspace/tasks/${id}/edit`}>Edit</Link>{actions.map(value=><button className={value==="done"?buttonClass:secondaryButtonClass} key={value} onClick={()=>void transition(value)}>{value==="todo"?"Reopen":value==="in_progress"?"Start":value.replaceAll("_"," ")}</button>)}</div>:undefined}/><div className="mt-7 grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]"><div className="grid gap-6"><section className={panel}><h2 className="font-semibold">Details</h2><p className="mt-3 whitespace-pre-wrap text-sm text-[var(--text-secondary)]">{task.description||"No description."}</p><div className="mt-4"><Progress value={task.progress}/></div></section><section className={panel}><h2 className="font-semibold">Checklist</h2>{task.checklist_items.map(item=>canManage?<form className="mt-3 grid min-h-11 gap-2 border-t border-[var(--border)] pt-3 sm:grid-cols-[auto_1fr_5rem_auto_auto]" key={item.id} onSubmit={event=>void updateChecklist(event,item)}><input aria-label={"Complete "+item.title} checked={item.is_completed} onChange={()=>void check(item)} type="checkbox"/><input className={fieldClass} defaultValue={item.title} name="title" aria-label="Checklist item title" required/><input className={fieldClass} defaultValue={item.sequence} min="1" name="sequence" type="number" aria-label="Checklist order"/><button className={secondaryButtonClass}>Save</button><button className={secondaryButtonClass} onClick={()=>void removeChecklist(item)} type="button">Remove</button></form>:<div className="mt-3 flex min-h-11 items-center gap-3 border-t border-[var(--border)] pt-3" key={item.id}><input checked={item.is_completed} disabled type="checkbox"/><span className={item.is_completed?"text-[var(--text-muted)] line-through":""}>{item.title}</span></div>)}{canManage&&<form className="mt-4 flex gap-2" onSubmit={add}><input className={fieldClass} name="title" placeholder="Checklist item" required/><button className={buttonClass}>Add Item</button></form>}</section></div><aside className={panel}><h2 className="font-semibold">Activity</h2>{task.activity?.map(item=><div className="mt-3 border-t border-[var(--border)] pt-3 text-sm" key={item.id}><p>{item.description}</p><p className="mt-1 text-xs text-[var(--text-muted)]">{item.actor||"System"} / {new Date(item.created_at).toLocaleString()}</p></div>)}</aside></div></Shell>;
}

export function ActivityPage() {
  const{activeOrganizationId}=useAuth();const[items,setItems]=useState<Activity[]>([]);const[domain,setDomain]=useState("");
  useEffect(()=>{if(activeOrganizationId)void apiRequest<Activity[]>(`/api/activity/?organization_id=${activeOrganizationId}${domain?`&domain=${domain}`:""}`).then(setItems)},[activeOrganizationId,domain]);
  return <Shell><PageHeader eyebrow="Governance" title="Activity" description="Curated organization activity, filtered by source permissions."/><label className="mt-6 block max-w-xs">Domain<select className={`mt-2 ${fieldClass}`} value={domain} onChange={e=>setDomain(e.target.value)}><option value="">All permitted activity</option>{["task","booking","callsheet","release","campaign","travel","production","document","contract","finance","rights"].map(value=><option key={value}>{value}</option>)}</select></label><div className="mt-7 grid gap-3">{items.map(item=><article className={panel} key={item.id}><div className="flex flex-wrap justify-between gap-3"><div><p className="font-medium">{item.description}</p><p className="mt-2 text-xs text-[var(--text-muted)]">{item.actor} / {item.action}</p></div><time className="text-xs text-[var(--text-muted)]">{new Date(item.created_at).toLocaleString()}</time></div>{item.destination&&<Link className="mt-3 inline-block text-sm text-amber-300" href={item.destination}>Open related record</Link>}</article>)}</div></Shell>;
}

export function SecurityPage() {
  const[items,setItems]=useState<{id:string;event_type:string;success:boolean;ip_address:string|null;client:string;occurred_at:string}[]>([]);const[message,setMessage]=useState("");
  useEffect(()=>{void apiRequest<typeof items>("/api/auth/security-activity/").then(setItems)},[]);
  async function change(event:FormEvent<HTMLFormElement>){event.preventDefault();const element=event.currentTarget;const form=new FormData(element);try{await apiRequest("/api/auth/change-password/",{method:"POST",body:JSON.stringify({current_password:form.get("current_password"),new_password:form.get("new_password")})});element.reset();setMessage("Password changed.")}catch(e){setMessage(e instanceof Error?e.message:"Unable to change password.")}}
  return <Shell><PageHeader eyebrow="Profile" title="Security" description="Recent login and password activity for your account."/><form className={`mt-7 grid max-w-xl gap-4 ${panel}`} onSubmit={change}><h2 className="font-semibold">Change Password</h2><label>Current password<input className={`mt-2 ${fieldClass}`} name="current_password" required type="password"/></label><label>New password<input className={`mt-2 ${fieldClass}`} minLength={12} name="new_password" required type="password"/></label><button className={buttonClass}>Change Password</button>{message&&<p aria-live="polite" className="text-sm">{message}</p>}</form><section className="mt-7"><h2 className="font-semibold">Recent Security Activity</h2><div className="mt-3 grid gap-3">{items.map(item=><article className={panel} key={item.id}><div className="flex flex-wrap justify-between gap-3"><span>{item.event_type.replaceAll("."," ")}</span><StatusBadge positive={item.success}>{item.success?"successful":"failed"}</StatusBadge></div><p className="mt-2 text-xs text-[var(--text-muted)]">{new Date(item.occurred_at).toLocaleString()} / {item.ip_address||"IP unavailable"} / {item.client||"Client unavailable"}</p></article>)}</div></section></Shell>;
}

export function ReauthenticatePage() {
  const router=useRouter();const[error,setError]=useState("");
  async function submit(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=new FormData(event.currentTarget);try{await apiRequest("/api/auth/reauthenticate/",{method:"POST",body:JSON.stringify({password:form.get("password")})});router.replace(new URLSearchParams(window.location.search).get("next")||"/dashboard")}catch(e){setError(e instanceof Error?e.message:"Unable to verify password.")} }
  async function signOut(){await apiRequest("/api/auth/logout/",{method:"POST"});router.replace("/login")}
  return <main className="grid min-h-dvh place-items-center bg-[var(--background)] px-5 py-10 text-[var(--text-primary)]"><section className="evolve-panel w-full max-w-md p-7 shadow-sm sm:p-10"><p className="evolve-eyebrow text-xs font-semibold uppercase">Security check</p><h1 className="evolve-display mt-3 text-3xl font-semibold">Confirm your identity</h1><p className="mt-4 text-sm leading-6 text-[var(--text-muted)]">Your secure session needs a fresh password confirmation before you continue to Global branding.</p><form className="mt-8 grid gap-4" onSubmit={submit}><label className="grid gap-2 text-sm text-[var(--text-secondary)]">Password<input autoFocus className={`min-h-12 ${fieldClass}`} name="password" required type="password"/></label>{error&&<p className="text-sm text-red-600" role="alert">{error}</p>}<button className={buttonClass}>Verify password</button><button className={secondaryButtonClass} onClick={()=>void signOut()} type="button">Sign out</button></form></section></main>;
}

export function TemplatesPage() {
  const{activeOrganizationId,session}=useAuth();const[items,setItems]=useState<Template[]>([]);const[selected,setSelected]=useState<Template|null>(null);const[message,setMessage]=useState("");
  const load=useCallback(()=>activeOrganizationId?apiRequest<Template[]>(`/api/document-templates/?organization_id=${activeOrganizationId}`).then(setItems):Promise.resolve(),[activeOrganizationId]);useEffect(()=>{void load()},[load]);
  async function create(event:FormEvent<HTMLFormElement>){event.preventDefault();if(!activeOrganizationId)return;const element=event.currentTarget;const form=new FormData(element);await apiRequest("/api/document-templates/",{method:"POST",body:JSON.stringify({...Object.fromEntries(form),organization_id:activeOrganizationId})});element.reset();await load()}
  async function uploadTemplate(event:React.ChangeEvent<HTMLInputElement>){
    const file=event.target.files?.[0]; if(!file||!activeOrganizationId)return;
    try{
      const body=await file.text();
      const key=file.name.replace(/\.[^.]+$/,"").toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"")||"uploaded-template";
      const created=await apiRequest<Template>("/api/document-templates/",{method:"POST",body:JSON.stringify({organization_id:activeOrganizationId,name:file.name.replace(/\.[^.]+$/,""),key:key+"-"+Date.now(),category:"general",document_type:"general",description:"Uploaded template",branding:{},})});
      await apiRequest("/api/document-templates/"+created.id+"/sections/",{method:"POST",body:JSON.stringify({organization_id:activeOrganizationId,key:"uploaded-content",title:"Uploaded content",body,sequence:1})});
      setMessage("Template uploaded. Configure its sections and branding."); await load();
    }catch(error){setMessage(error instanceof Error?error.message:"Unable to upload template.");}
  }
  async function addSection(event:FormEvent<HTMLFormElement>){event.preventDefault();if(!selected||!activeOrganizationId)return;const element=event.currentTarget;await apiRequest(`/api/document-templates/${selected.id}/sections/`,{method:"POST",body:JSON.stringify({...Object.fromEntries(new FormData(element)),organization_id:activeOrganizationId})});element.reset();setMessage("Section added. Reopen the template to refresh its version.");await load()}
  async function updateBranding(event:FormEvent<HTMLFormElement>){
    event.preventDefault(); if(!selected||!activeOrganizationId)return;
    const values=Object.fromEntries(new FormData(event.currentTarget));
    const branding={logo_url:String(values.logo_url||""),header_text:String(values.header_text||""),footer_text:String(values.footer_text||""),primary_color:String(values.primary_color||"#8A5A00"),accent_color:String(values.accent_color||"#A86B00")};
    const refreshed=await apiRequest<Template>("/api/document-templates/"+selected.id+"/",{method:"PATCH",body:JSON.stringify({organization_id:activeOrganizationId,branding})});
    setSelected(refreshed); setMessage("Template branding saved."); await load();
  }
  async function uploadLogo(file: File){
    if(!selected||!activeOrganizationId)return;
    try {
      const body=new FormData(); body.set("organization_id",activeOrganizationId); body.set("file",file);
      const refreshed=await apiRequest<Template>(`/api/document-templates/${selected.id}/branding/logo/`,{method:"POST",body});
      setSelected(refreshed); setMessage("Template logo uploaded to private storage."); await load();
    } catch(error) { setMessage(error instanceof Error?error.message:"Unable to upload template logo."); }
  }
  async function updateSection(event:FormEvent<HTMLFormElement>,section:TemplateSection){event.preventDefault();if(!selected||!activeOrganizationId)return;const values=Object.fromEntries(new FormData(event.currentTarget));await apiRequest(`/api/document-templates/${selected.id}/sections/${section.id}/`,{method:"PATCH",body:JSON.stringify({...values,is_enabled:values.is_enabled==="on",organization_id:activeOrganizationId})});setMessage("Section updated.");const refreshed=await apiRequest<Template>(`/api/document-templates/${selected.id}/?organization_id=${activeOrganizationId}`);setSelected(refreshed);await load()}
  const canManage=hasOrganizationPermission(session,activeOrganizationId,"document_template.manage");
  const canGenerate=hasOrganizationPermission(session,activeOrganizationId,"document.manage");
  const editable=selected?.organization===activeOrganizationId&&hasOrganizationPermission(session,activeOrganizationId,"document_template.manage");
  return <Shell><PageHeader eyebrow="Documents" title="Template workspace" description="Configure booking, call-sheet, travel, and operational templates. Active defaults drive generation while preserving historical snapshots." actions={canManage?<div className="flex flex-wrap gap-2"><button className={secondaryButtonClass} onClick={async()=>{await apiRequest(`/api/document-templates/bootstrap/`,{method:"POST",body:JSON.stringify({organization_id:activeOrganizationId})});setMessage("Starter booking and call-sheet templates created.");await load()}}>Create starter templates</button><button className={secondaryButtonClass} onClick={()=>setSelected(null)}>New Template</button><label className={secondaryButtonClass+" cursor-pointer"}>Upload template<input className="sr-only" type="file" accept=".txt,.md" onChange={(event)=>void uploadTemplate(event)}/></label></div>:undefined}/><div className="mt-7 grid gap-6 lg:grid-cols-[20rem_minmax(0,1fr)]"><aside className="grid content-start gap-2">{items.map(item=><button className={`${panel} text-left`} key={item.id} onClick={()=>setSelected(item)}><span className="font-medium">{item.name}</span><span className="mt-1 block text-xs text-[var(--text-muted)]">{item.category || "general"} · v{item.version} / {item.status}{item.organization?"":" / platform"}</span></button>)}</aside><section className={panel}>{!selected?canManage?<form className="grid gap-4" onSubmit={create}><h2 className="font-semibold">New Template</h2><input className={fieldClass} name="name" placeholder="Template name" required/><input className={fieldClass} name="key" placeholder="template-key" required/><select className={fieldClass} name="category">{["general","management","bookings","live","music","campaign","travel"].map(value=><option key={value}>{value}</option>)}</select><select className={fieldClass} name="document_type">{["booking_confirmation","booking_brief","call_sheet","invoice","performance_agreement","contract_summary","invoice_cover","travel_itinerary","production_advance","general"].map(value=><option key={value}>{value}</option>)}</select><label className="flex items-center gap-2 text-sm"><input name="is_default" type="checkbox"/>Set as default for this document type</label><textarea className="min-h-24 rounded-md border border-[var(--border)] bg-[var(--surface)] p-3" name="description" placeholder="Description"/><button className={buttonClass}>Create Template</button></form>:<EmptyState title="Select a template" detail="Template management requires permission."/>:<div><div className="flex flex-wrap justify-between gap-3"><div><h2 className="font-semibold">{selected.name}</h2><p className="text-sm text-[var(--text-muted)]">Category: {selected.category || "general"} · {selected.is_default ? "Default template" : "Optional template"}</p>{editable&&<form className="mt-4 grid gap-3 rounded-md border border-[var(--border)] p-4" onSubmit={updateBranding}><p className="text-sm font-medium">Template branding</p><label className="grid gap-2 text-sm text-[var(--text-secondary)]">Upload logo asset<input className={fieldClass} type="file" accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp" onChange={(event)=>{const file=event.target.files?.[0];if(file)void uploadLogo(file)}}/></label><input className={fieldClass} name="logo_url" defaultValue={selected.branding?.logo_url||""} placeholder="Logo URL (optional)"/><input className={fieldClass} name="header_text" defaultValue={selected.branding?.header_text||""} placeholder="Header text"/><input className={fieldClass} name="footer_text" defaultValue={selected.branding?.footer_text||""} placeholder="Footer text"/><div className="grid gap-3 sm:grid-cols-2"><label className="text-xs text-[var(--text-muted)]">Primary color<input className={fieldClass} name="primary_color" defaultValue={selected.branding?.primary_color||"#8A5A00"} pattern="#[0-9A-Fa-f]{6}"/></label><label className="text-xs text-[var(--text-muted)]">Accent color<input className={fieldClass} name="accent_color" defaultValue={selected.branding?.accent_color||"#A86B00"} pattern="#[0-9A-Fa-f]{6}"/></label></div><button className={secondaryButtonClass}>Save template branding</button></form>}<div className="mt-4 overflow-hidden rounded-xl border bg-white text-neutral-900 shadow-sm" style={{borderColor:selected.branding?.accent_color||"#d6d3d1"}}><div className="border-b-4 p-6" style={{borderColor:selected.branding?.primary_color||"#8A5A00"}}>{selected.branding?.logo_url&&<img className="mb-5 max-h-14 max-w-56 object-contain object-left" src={selected.branding.logo_url} alt="Template logo"/>}<p className="text-xs font-semibold uppercase tracking-[0.16em]" style={{color:selected.branding?.accent_color||"#A86B00"}}>{selected.branding?.header_text||"Document preview"}</p><h3 className="mt-3 text-2xl font-semibold">{selected.name}</h3><p className="mt-1 text-sm text-[var(--text-muted)]">{selected.document_type.replaceAll("_"," ")} · version {selected.version}</p></div><div className="grid gap-5 p-6">{selected.sections.filter((section)=>section.is_enabled).map((section)=><section className="border-b border-neutral-200 pb-4 last:border-0" key={section.id}><h4 className="font-semibold">{section.title}</h4><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-neutral-600">{section.body||"Empty section"}</p></section>)}{!selected.sections.length&&<p className="text-sm text-[var(--text-muted)]">Add sections to see the complete document preview.</p>}</div>{selected.branding?.footer_text&&<div className="border-t border-neutral-200 px-6 py-4 text-xs text-[var(--text-muted)]">{selected.branding.footer_text}</div>}</div><details className="mt-2"><summary className="cursor-pointer text-sm text-[var(--accent-strong)]">Insert Variable</summary><div className="mt-2 flex flex-wrap gap-2">{selected.variables.map(variable=><button type="button" className="rounded border border-[var(--border)] px-2 py-1 text-xs" key={variable} onClick={()=>void navigator.clipboard?.writeText(`{{ ${variable} }}`)}>[ {variable} ]</button>)}</div></details></div>{editable&&<div className="flex gap-2"><button className={secondaryButtonClass} onClick={async()=>{await apiRequest(`/api/document-templates/${selected.id}/${selected.status==="active"?"inactive":"active"}/`,{method:"POST",body:JSON.stringify({organization_id:activeOrganizationId})});await load()}}>{selected.status==="active"?"Deactivate":"Activate"}</button>{selected.status==="active"&&!selected.is_default&&<button className={secondaryButtonClass} onClick={async()=>{await apiRequest(`/api/document-templates/${selected.id}/set-default/`,{method:"POST",body:JSON.stringify({organization_id:activeOrganizationId})});setMessage("Default template updated.");const refreshed=await apiRequest<Template>(`/api/document-templates/${selected.id}/?organization_id=${activeOrganizationId}`);setSelected(refreshed);await load()}}>Set as default</button>}<button className={secondaryButtonClass} onClick={async()=>{await apiRequest(`/api/document-templates/${selected.id}/duplicate/`,{method:"POST",body:JSON.stringify({organization_id:activeOrganizationId,key:`${selected.key}-copy`})});await load()}}>Duplicate</button></div>}</div><div className="mt-5 grid gap-3">{selected.sections.map(section=>editable?<form className="grid gap-3 rounded-md border border-[var(--border)] p-4" key={section.id} onSubmit={event=>void updateSection(event,section)}><input className={fieldClass} defaultValue={section.title} name="title" required/><textarea className="min-h-28 rounded-md border border-[var(--border)] bg-[var(--surface)] p-3" defaultValue={section.body} name="body" required/><div className="flex flex-wrap items-center gap-3"><input className={fieldClass + " w-24"} defaultValue={section.sequence} min="1" name="sequence" type="number"/><label className="flex items-center gap-2 text-sm"><input defaultChecked={section.is_enabled} name="is_enabled" type="checkbox"/>Enabled</label><button className={secondaryButtonClass}>Save Section</button></div></form>:<article className="rounded-md border border-[var(--border)] p-4" key={section.id}><h3 className="font-medium">{section.title}</h3><p className="mt-2 whitespace-pre-wrap text-sm text-[var(--text-secondary)]">{section.body}</p></article>)}</div><>{canGenerate&&<TemplateGeneration template={selected}/>}{editable&&<form className="mt-5 grid gap-3 border-t border-[var(--border)] pt-5" onSubmit={addSection}><h3 className="font-medium">Add Section</h3><input className={fieldClass} name="key" placeholder="section-key" required/><input className={fieldClass} name="title" placeholder="Section title" required/><textarea className="min-h-32 rounded-md border border-[var(--border)] bg-[var(--surface)] p-3" name="body" placeholder="Use an available {{ variable }}" required/><input className={fieldClass} defaultValue={selected.sections.length+1} min="1" name="sequence" type="number"/><button className={buttonClass}>Add Section</button></form>}{message&&<p className="mt-4 text-sm">{message}</p>}</></div>}</section></div></Shell>;
}

export function ReleaseTasks({ releaseId, platform = false }: { releaseId: string; platform?: boolean }) {
  const { activeOrganizationId, session } = useAuth();
  const canManage = hasOrganizationPermission(session, activeOrganizationId, "task.manage");
  const [items, setItems] = useState<Task[]>([]);
  const load = useCallback(() => activeOrganizationId ? apiRequest<Task[]>("/api/tasks/?organization_id="+activeOrganizationId+"&release="+releaseId).then(setItems) : Promise.resolve(), [activeOrganizationId, releaseId]);
  useEffect(() => { if (!platform) void load(); }, [load, platform]);
  const progress = useMemo(() => ({ complete: items.filter(item => item.status === "done").length, total: items.filter(item => item.status !== "cancelled").length, percent: items.some(item => item.status !== "cancelled") ? Math.round(items.filter(item => item.status === "done").length * 100 / items.filter(item => item.status !== "cancelled").length) : 0 }), [items]);
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!activeOrganizationId) return;
    const element = event.currentTarget; const form = new FormData(element);
    await apiRequest("/api/tasks/", { method: "POST", body: JSON.stringify({ organization_id: activeOrganizationId, release: releaseId, title: form.get("title"), priority: form.get("priority"), due_at: form.get("due_at") || null }) });
    element.reset(); await load();
  }
  if (platform) return null;
  return <section className={panel}><div className="flex flex-wrap justify-between gap-4"><div><h2 className="font-semibold">Release Tasks</h2><div className="mt-2 w-56"><Progress value={progress}/></div></div></div><div className="mt-4 grid gap-2">{items.map(item=><Link className="grid gap-2 border-t border-[var(--border)] pt-3 sm:grid-cols-[1fr_auto_auto]" href={`/workspace/tasks/${item.id}`} key={item.id}><span>{item.title}</span><span>{item.assignee?.name||"Unassigned"}</span><span>{item.status.replaceAll("_"," ")} / {item.progress.complete}/{item.progress.total}</span></Link>)}</div>{canManage&&<form className="mt-5 grid gap-2 sm:grid-cols-[1fr_10rem_13rem_auto]" onSubmit={create}><input className={fieldClass} name="title" placeholder="Release task" required/><select className={fieldClass} name="priority">{priorities.map(value=><option key={value}>{value}</option>)}</select><input className={fieldClass} name="due_at" type="datetime-local"/><button className={buttonClass}>Add Task</button></form>}</section>;
}

export function TemplateGeneration({ template }: { template: Template }) {
  const { activeOrganizationId } = useAuth();
  const router = useRouter();
  const [bookings, setBookings] = useState<Array<{ id: string; reference: string; title: string; event_date: string; artist?: { stage_name: string }; venue_name_snapshot?: string }>>([]);
  const [bookingId, setBookingId] = useState("");
  const [bookingQuery, setBookingQuery] = useState("");
  const [preview, setPreview] = useState("");
  const [missing, setMissing] = useState<string[]>([]);
  const [branding, setBranding] = useState<Record<string, string>>({});
  useEffect(() => {
    if (!activeOrganizationId) return;
    void apiRequest<typeof bookings>(`/api/bookings/?organization_id=${activeOrganizationId}`).then(setBookings);
  }, [activeOrganizationId]);
  const visibleBookings = bookings.filter((booking) => {
    const text = `${booking.reference} ${booking.title} ${booking.artist?.stage_name || ""} ${booking.venue_name_snapshot || ""}`.toLowerCase();
    return text.includes(bookingQuery.toLowerCase());
  });
  async function previewDocument() {
    const result = await apiRequest<{content:string;missing_variables:string[];branding:Record<string,string>}>(`/api/document-templates/${template.id}/preview/`, { method: "POST", body: JSON.stringify({ organization_id: activeOrganizationId, booking_id: bookingId }) });
    setPreview(result.content); setMissing(result.missing_variables); setBranding(result.branding);
  }
  async function generate() {
    const result = await apiRequest<{id:string}>(`/api/document-templates/${template.id}/generate/`, { method: "POST", body: JSON.stringify({ organization_id: activeOrganizationId, booking_id: bookingId, title: `${template.name} document` }) });
    router.push(`/workspace/documents/${result.id}`);
  }
  return <section className="mt-6 border-t border-[var(--border)] pt-5"><h3 className="font-medium">Preview and Generate</h3><label className="mt-3 block">Find a booking<input className={`mt-2 ${fieldClass}`} placeholder="Search reference, event, artist or venue" value={bookingQuery} onChange={event=>setBookingQuery(event.target.value)}/></label><label className="mt-3 block">Booking<select className={`mt-2 ${fieldClass}`} value={bookingId} onChange={event=>setBookingId(event.target.value)} required><option value="">Select a booking</option>{visibleBookings.map(booking=><option key={booking.id} value={booking.id}>{booking.reference} · {booking.title} · {booking.event_date}{booking.artist?.stage_name?` · ${booking.artist.stage_name}`:""}</option>)}</select></label><p className="mt-2 text-xs text-[var(--text-muted)]">Only bookings available to your organization account are shown.</p><div className="mt-3 flex gap-2"><button className={secondaryButtonClass} disabled={!bookingId} onClick={()=>void previewDocument()}>Preview</button><button className={buttonClass} disabled={!bookingId||template.status!=="active"} onClick={()=>void generate()}>Generate Document</button></div>{preview&&<article className="mt-5 overflow-hidden rounded-md border bg-white text-neutral-900 shadow-sm" style={{borderColor:branding.accent||"#d6d3d1"}}><header className="border-b-4 p-5" style={{borderColor:branding.primary||"#8A5A00"}}>{branding.logo_url&&<img className="mb-4 max-h-12 max-w-52 object-contain object-left" src={branding.logo_url} alt={branding.brand_name||"Brand logo"}/>}<p className="text-xs font-semibold uppercase tracking-[0.16em]" style={{color:branding.accent||"#A86B00"}}>{branding.header_text||branding.brand_name||"Evolve document"}</p><h3 className="mt-2 text-xl font-semibold">{template.name}</h3></header><div className="whitespace-pre-wrap p-5 text-sm leading-6">{preview}</div>{branding.footer_text&&<footer className="border-t border-neutral-200 px-5 py-3 text-xs text-neutral-500">{branding.footer_text}</footer>}</article>}{missing.length>0&&<p className="mt-3 text-sm text-amber-300">Missing values: {missing.join(", ")}</p>}</section>;
}
