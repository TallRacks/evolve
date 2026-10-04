"use client";

import { Bell } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { apiRequest } from "@/lib/api/client";

type Notification = { id: string; title: string; message: string; action_url: string; read_at: string | null };
type NotificationPage = { count: number; results: Notification[] };

export function NotificationBell() {
  const [count, setCount] = useState(0);
  const [items, setItems] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);
  const [pushStatus, setPushStatus] = useState<"unknown" | "enabled" | "unavailable" | "blocked">("unknown");
  const wrapper = useRef<HTMLDivElement>(null);

  async function load() {
    const [unread, page] = await Promise.all([
      apiRequest<{ count: number }>("/api/notifications/unread-count/"),
      apiRequest<NotificationPage>("/api/notifications/?page=1"),
    ]);
    setCount(unread.count);
    setItems(page.results.slice(0, 5));
  }

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void load().catch(() => {}), 0);
    const onFocus = () => void load().catch(() => {});
    const onPointerDown = (event: PointerEvent) => {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false);
    };
    window.addEventListener("focus", onFocus);
    window.addEventListener("pointerdown", onPointerDown);
    return () => {
      window.clearTimeout(initialLoad);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("pointerdown", onPointerDown);
    };
  }, []);

  function decodeKey(value: string) {
    const padded = value + "=".repeat((4 - (value.length % 4)) % 4);
    const raw = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
    return Uint8Array.from(raw, (char) => char.charCodeAt(0));
  }

  async function enablePush() {
    if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
      setPushStatus("unavailable"); return;
    }
    const permission = await Notification.requestPermission();
    if (permission !== "granted") { setPushStatus("blocked"); return; }
    const config = await apiRequest<{ enabled: boolean; public_key: string }>("/api/notifications/push-subscription/");
    if (!config.enabled || !config.public_key) { setPushStatus("unavailable"); return; }
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: decodeKey(config.public_key) });
    await apiRequest("/api/notifications/push-subscription/", { method: "POST", body: JSON.stringify(subscription.toJSON()) });
    setPushStatus("enabled");
  }

  return <div className="relative" ref={wrapper}>
    <button aria-expanded={open} aria-haspopup="menu" aria-label={`${count} unread notifications`} className="relative grid size-10 place-items-center rounded-md border border-neutral-800" onClick={() => setOpen((value) => !value)} title="Notifications" type="button">
      <Bell size={18}/>{count > 0 && <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-red-500 px-1 text-center text-xs text-white">{count > 99 ? "99+" : count}</span>}
    </button>
    {open && <div className="absolute right-0 z-50 mt-2 w-[min(22rem,calc(100vw-2rem))] rounded-md border border-neutral-800 bg-neutral-950 p-2 shadow-xl" role="menu">
      <div className="flex items-center justify-between px-2 py-2"><strong className="text-sm">Notifications</strong><div className="flex items-center gap-2"><button className="text-xs text-amber-300" onClick={() => void enablePush().catch(() => setPushStatus("unavailable"))} type="button">{pushStatus === "enabled" ? "Alerts enabled" : "Enable alerts"}</button><Link className="text-xs text-amber-300" href="/workspace/notifications">View all</Link></div></div>
      {items.length ? items.map((item) => <Link className="block border-t border-neutral-800 px-2 py-3 text-sm hover:bg-neutral-900" href={item.action_url || "/workspace/notifications"} key={item.id} onClick={() => setOpen(false)} role="menuitem"><span className="flex items-center gap-2 font-medium">{!item.read_at && <span className="size-2 rounded-full bg-amber-400"/>}{item.title}</span><span className="mt-1 line-clamp-2 block text-xs text-neutral-400">{item.message}</span></Link>) : <p className="px-2 py-5 text-sm text-neutral-500">No notifications</p>}
    </div>}
  </div>;
}
