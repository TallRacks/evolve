"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiRequest } from "@/lib/api/client";
import { buttonClass, secondaryButtonClass } from "@/components/ui/page";

// Permission contracts: booking.manage and music.manage remain backend-authorized.
const BOOKING_ACTIONS = [
  ["booking-brief", "Create Booking Brief"],
  ["show-day-brief", "Create Show-Day Brief"],
  ["production-notes", "Create Production Notes"],
  ["meeting-note", "Create Meeting Note"],
] as const;
const RELEASE_ACTIONS = [
  ["release-one-sheet", "Create Release One-Sheet"],
  ["metadata-sheet", "Create Metadata Sheet"],
  ["credits-sheet", "Create Credits Sheet"],
  ["campaign-brief", "Create Campaign Brief"],
  ["release-checklist", "Create Release Checklist"],
] as const;

export function OfficeGeneratorActions({ source, id, canManage }: { source: "booking" | "release"; id: string; canManage: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  if (!canManage) return null;
  const actions = source === "booking" ? BOOKING_ACTIONS : RELEASE_ACTIONS;
  async function generate(key: string) {
    setBusy(key); setError("");
    try {
      const result = await apiRequest<{ document: string }>(`/api/${source === "booking" ? "bookings" : "music/releases"}/${id}/office/${key}/`, { method: "POST" });
      router.push(`/workspace/office/${result.document}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create Office item.");
    } finally { setBusy(""); }
  }
  return <section className="rounded-md border border-neutral-800 bg-neutral-900 p-4" aria-label="Office generators"><h2 className="font-semibold">Office / Documents</h2><p className="mt-1 text-sm text-neutral-500">Create a linked working document from authoritative source data.</p><div className="mt-3 flex flex-wrap gap-2">{actions.map(([key, label], index) => <button className={index === 0 ? buttonClass : secondaryButtonClass} disabled={Boolean(busy)} key={key} onClick={() => void generate(key)} type="button">{busy === key ? "Creating…" : label}</button>)}</div>{error && <p className="mt-3 text-sm text-red-300" role="alert">{error}</p>}</section>;
}
