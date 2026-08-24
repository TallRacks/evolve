"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { RouteGuard } from "@/components/auth/route-guard";
import { apiRequest } from "@/lib/api/client";
import { buttonClass, EmptyState, fieldClass, PageHeader, StatusBadge } from "@/components/ui/page";

interface Organization { id: string; name: string }
interface Artist { id: string; organization: Organization; stage_name: string; slug: string; status: string; team_count: number; portal_user_count: number }

export function PlatformArtistDirectoryPage() {
  const [artists,setArtists]=useState<Artist[]>([]); const [organizations,setOrganizations]=useState<Organization[]>([]); const [query,setQuery]=useState(""); const [status,setStatus]=useState(""); const [message,setMessage]=useState("");
  const load=useCallback(async()=>setArtists(await apiRequest<Artist[]>("/api/platform/artists/")),[]);
  useEffect(()=>{let cancelled=false;Promise.all([apiRequest<Artist[]>("/api/platform/artists/"),apiRequest<Organization[]>("/api/platform/organizations/")]).then(([nextArtists,nextOrganizations])=>{if(!cancelled){setArtists(nextArtists);setOrganizations(nextOrganizations)}});return()=>{cancelled=true}},[]);
  const filtered=useMemo(()=>artists.filter((item)=>(!query||`${item.stage_name} ${item.organization.name}`.toLowerCase().includes(query.toLowerCase()))&&(!status||item.status===status)),[artists,query,status]);
  async function create(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=new FormData(event.currentTarget);try{await apiRequest("/api/platform/artists/",{method:"POST",body:JSON.stringify({organization_id:form.get("organization_id"),stage_name:form.get("stage_name"),slug:form.get("slug"),status:"active"})});event.currentTarget.reset();setMessage("Artist created.");await load()}catch(caught){setMessage(caught instanceof Error?caught.message:"Unable to create artist.")}}
  return <RouteGuard portal="platform"><AppShell><PageHeader eyebrow="Platform" title="Artists" description="Cross-organization artist inventory."/><form className="mt-6 grid gap-3 rounded-md border border-neutral-800 bg-neutral-900 p-4 sm:grid-cols-[1fr_1fr_1fr_auto]" onSubmit={create}><select className={fieldClass} name="organization_id" required><option value="">Organization</option>{organizations.map((item)=><option key={item.id} value={item.id}>{item.name}</option>)}</select><input className={fieldClass} name="stage_name" placeholder="Stage name" required/><input className={fieldClass} name="slug" placeholder="artist-slug" required/><button className={buttonClass}>Create</button></form>{message&&<p className="mt-3 text-sm text-amber-300">{message}</p>}<div className="mt-6 grid gap-3 sm:grid-cols-2"><input className={fieldClass} placeholder="Search artist or organization" value={query} onChange={(event)=>setQuery(event.target.value)}/><select className={fieldClass} value={status} onChange={(event)=>setStatus(event.target.value)}><option value="">All statuses</option>{["active","inactive","archived"].map((value)=><option key={value}>{value}</option>)}</select></div>{filtered.length===0?<div className="mt-7"><EmptyState title="No artists" detail="No artist profiles match these filters."/></div>:<div className="mt-7 grid gap-3">{filtered.map((artist)=><Link className="grid gap-3 rounded-md border border-neutral-800 bg-neutral-900 p-5 sm:grid-cols-[1fr_auto_auto_auto]" href={`/platform/artists/${artist.id}`} key={artist.id}><div><p>{artist.stage_name}</p><p className="text-sm text-neutral-500">{artist.organization.name}</p></div><span>{artist.team_count} team</span><span>{artist.portal_user_count} portal</span><StatusBadge positive={artist.status==="active"}>{artist.status}</StatusBadge></Link>)}</div>}</AppShell></RouteGuard>;
}
