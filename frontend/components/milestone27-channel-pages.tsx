"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { RouteGuard } from "@/components/auth/route-guard";
import { apiRequest } from "@/lib/api/client";

type ChannelData = { connectors: { id: string; provider: string; name: string; status: string; active: boolean; display_name: string; display_phone: string }[]; identities: { id: string; provider: string; organization: string; active: boolean; revoked: boolean }[] };

export function PlatformChannelsPage() {
  const [data, setData] = useState<ChannelData | null>(null);
  useEffect(() => { void apiRequest<ChannelData>("/api/platform/channels/?platform=true").then(setData); }, []);
  return <RouteGuard portal="platform"><AppShell><main className="p-4 sm:p-8"><p className="text-xs uppercase tracking-[0.2em] text-amber-400">Platform</p><h1 className="mt-2 text-3xl font-semibold">Channels</h1><p className="mt-2 text-neutral-400">Provider metadata only. Secrets remain external and configuration is never fabricated.</p><div className="mt-8 grid gap-4 sm:grid-cols-2">{["whatsapp", "email"].map((provider) => { const rows = data?.connectors.filter((item) => item.provider === provider) ?? []; return <section className="rounded-xl border border-neutral-800 p-5" key={provider}><h2 className="font-medium">{provider === "whatsapp" ? "WhatsApp Business" : "Inbound Email"}</h2><p className="mt-2 text-sm text-neutral-500">{rows.length ? rows.map((item) => `${item.name} · ${item.status}`).join(", ") : "Not configured"}</p></section>; })}</div></main></AppShell></RouteGuard>;
}

export function ProfileChannelsPage() {
  const [data, setData] = useState<ChannelData | null>(null);
  useEffect(() => { void apiRequest<ChannelData>("/api/workspace/channels/").then(setData); }, []);
  return <RouteGuard portal="workspace"><AppShell organizationScoped><main className="p-4 sm:p-8"><p className="text-xs uppercase tracking-[0.2em] text-amber-400">Profile</p><h1 className="mt-2 text-3xl font-semibold">Connected channels</h1><div className="mt-8 space-y-3">{data?.identities.map((identity) => <div className="rounded-xl border border-neutral-800 p-4" key={identity.id}><p className="font-medium">{identity.provider}</p><p className="mt-1 text-sm text-neutral-500">{identity.organization} · {identity.revoked ? "Revoked" : identity.active ? "Connected" : "Inactive"}</p></div>)}{!data?.identities.length && <p className="rounded-xl border border-dashed border-neutral-700 p-6 text-sm text-neutral-500">No connected channels. A platform administrator must configure a provider first.</p>}</div></main></AppShell></RouteGuard>;
}
