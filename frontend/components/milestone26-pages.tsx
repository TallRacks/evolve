"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { RouteGuard } from "@/components/auth/route-guard";
import { useAuth } from "@/components/auth/auth-provider";
import { apiRequest } from "@/lib/api/client";

function Frame({ children }: { children: React.ReactNode }) {
  return <RouteGuard portal="workspace"><AppShell organizationScoped>{children}</AppShell></RouteGuard>;
}

export function CopilotPage() {
  const { activeOrganizationId } = useAuth();
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("Ask about today, overdue tasks, or bookings.");
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!activeOrganizationId || !message.trim()) return;
    const result = await apiRequest<{ message: string; status: string }>("/api/workspace/copilot/", { method: "POST", body: JSON.stringify({ organization_id: activeOrganizationId, message }) });
    setAnswer(result.message);
  }
  return <Frame><main className="mx-auto flex min-h-[calc(100vh-8rem)] max-w-3xl flex-col p-4 sm:p-8"><div className="mb-8"><p className="text-xs uppercase tracking-[0.2em] text-amber-400">Evolve Copilot</p><h1 className="mt-2 text-3xl font-semibold">Work, in conversation.</h1><p className="mt-2 text-neutral-400">Copilot can inspect your workspace and propose safe actions. It never replaces your permissions.</p></div><div className="flex-1 rounded-2xl border border-neutral-800 bg-neutral-950 p-5"><p className="text-sm text-neutral-300" aria-live="polite">{answer}</p></div><form onSubmit={submit} className="mt-4 flex gap-2"><input value={message} onChange={(event) => setMessage(event.target.value)} placeholder="What’s happening today?" className="min-w-0 flex-1 rounded-xl border border-neutral-700 bg-neutral-900 px-4 py-3 text-sm" aria-label="Copilot message" /><button className="rounded-xl bg-amber-400 px-5 py-3 text-sm font-semibold text-black">Ask</button></form></main></Frame>;
}

export function MyWorkPage() {
  const { activeOrganizationId } = useAuth();
  const [data, setData] = useState<{ tasks: { id: string; title: string; status: string; overdue: boolean }[]; notifications: number } | null>(null);
  useEffect(() => { if (activeOrganizationId) void apiRequest<typeof data>(`/api/workspace/my-work/?organization_id=${activeOrganizationId}`).then(setData); }, [activeOrganizationId]);
  return <Frame><main className="p-4 sm:p-8"><p className="text-xs uppercase tracking-[0.2em] text-amber-400">Home</p><h1 className="mt-2 text-3xl font-semibold">My Work</h1><p className="mt-2 text-neutral-400">Assigned tasks and attention items from your current workspace.</p><section className="mt-8 grid gap-3 sm:grid-cols-3"><div className="rounded-xl border border-neutral-800 p-4"><p className="text-xs text-neutral-500">Assigned tasks</p><p className="mt-2 text-2xl">{data?.tasks.length ?? "—"}</p></div><div className="rounded-xl border border-neutral-800 p-4"><p className="text-xs text-neutral-500">Unread notifications</p><p className="mt-2 text-2xl">{data?.notifications ?? "—"}</p></div></section><div className="mt-8 space-y-2">{data?.tasks.map((task) => <Link href={`/workspace/tasks/${task.id}`} key={task.id} className="flex items-center justify-between rounded-xl border border-neutral-800 bg-neutral-950 p-4"><span>{task.title}</span><span className="text-xs text-neutral-400">{task.overdue ? "Overdue" : task.status}</span></Link>)}</div></main></Frame>;
}

export function InboxPage() {
  const [data, setData] = useState<{ notifications: { id: string; title: string; message: string }[]; ai_confirmations: { id: string; action_key: string; risk: string }[] } | null>(null);
  useEffect(() => { void apiRequest<typeof data>("/api/workspace/inbox/").then(setData); }, []);
  return <Frame><main className="p-4 sm:p-8"><p className="text-xs uppercase tracking-[0.2em] text-amber-400">Home</p><h1 className="mt-2 text-3xl font-semibold">Inbox</h1><p className="mt-2 text-neutral-400">Notifications and confirmations in one place.</p><section className="mt-8 space-y-3">{data?.ai_confirmations.map((item) => <div key={item.id} className="rounded-xl border border-amber-700/50 bg-amber-950/20 p-4"><p className="font-medium">Confirm {item.action_key}</p><p className="mt-1 text-sm text-neutral-400">{item.risk} risk · confirmation required</p></div>)}{data?.notifications.map((item) => <div key={item.id} className="rounded-xl border border-neutral-800 p-4"><p className="font-medium">{item.title}</p><p className="mt-1 text-sm text-neutral-400">{item.message}</p></div>)}</section></main></Frame>;
}

export function BoardsPage() { return <Frame><main className="p-4 sm:p-8"><p className="text-xs uppercase tracking-[0.2em] text-amber-400">Workspace</p><h1 className="mt-2 text-3xl font-semibold">Operational boards</h1><p className="mt-2 text-neutral-400">Authoritative views over Tasks, Bookings, Production, Campaigns and Releases.</p><div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{["Tasks", "Bookings", "Production", "Campaigns", "Releases"].map((name) => <div key={name} className="rounded-xl border border-neutral-800 p-5"><h2 className="font-medium">{name}</h2><p className="mt-2 text-sm text-neutral-500">List and grouped status view</p></div>)}</div></main></Frame>; }

export function ApprovalsPage() { return <Frame><main className="p-4 sm:p-8"><p className="text-xs uppercase tracking-[0.2em] text-amber-400">Workspace</p><h1 className="mt-2 text-3xl font-semibold">Approvals</h1><p className="mt-2 text-neutral-400">Contract approvals stay inside the existing contract lifecycle.</p><div className="mt-8 rounded-xl border border-neutral-800 p-5">No pending approvals for this workspace.</div></main></Frame>; }

export function AutomationsPage() { return <Frame><main className="p-4 sm:p-8"><p className="text-xs uppercase tracking-[0.2em] text-amber-400">Workspace</p><h1 className="mt-2 text-3xl font-semibold">Automations</h1><p className="mt-2 text-neutral-400">Safe event-driven rules with allowlisted events and actions.</p><div className="mt-8 rounded-xl border border-neutral-800 p-5">No automations configured.</div></main></Frame>; }

export function AISettingsPage() { return <RouteGuard portal="platform"><AppShell><main className="p-4 sm:p-8"><p className="text-xs uppercase tracking-[0.2em] text-amber-400">Platform</p><h1 className="mt-2 text-3xl font-semibold">AI provider</h1><p className="mt-4 rounded-xl border border-neutral-800 p-5 text-neutral-400">AI Not Configured · no provider secret is stored by Evolve.</p></main></AppShell></RouteGuard>; }
export function ChannelsPage() { return <Frame><main className="p-4 sm:p-8"><p className="text-xs uppercase tracking-[0.2em] text-amber-400">Profile</p><h1 className="mt-2 text-3xl font-semibold">Connected channels</h1><p className="mt-2 text-neutral-400">Official-provider connections are opt-in and identity-linked.</p><div className="mt-8 grid gap-4 sm:grid-cols-2"><div className="rounded-xl border border-neutral-800 p-5"><h2 className="font-medium">WhatsApp</h2><p className="mt-2 text-sm text-neutral-500">Not connected · phone number alone never grants access.</p></div><div className="rounded-xl border border-neutral-800 p-5"><h2 className="font-medium">Email Agent</h2><p className="mt-2 text-sm text-neutral-500">Disabled · inbound email is not configured.</p></div></div></main></Frame>; }
