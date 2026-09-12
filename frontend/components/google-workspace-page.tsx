import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { RouteGuard } from "@/components/auth/route-guard";
import { PageHeader, secondaryButtonClass, StatusBadge } from "@/components/ui/page";

const cards = [
  ["Google Docs", "Create a Doc from an Evolve entity, then open it in Google for editing."],
  ["Google Sheets", "Create planning, metadata, checklist, or pitch-tracker Sheets without making Google the Finance source of truth."],
  ["Link Drive files", "Link an existing Google file to an Evolve Document by authorized provider metadata only."],
];

export function GoogleWorkspacePage() {
  return <RouteGuard portal="platform"><AppShell><PageHeader eyebrow="Platform integration" title="Google Workspace" description="A controlled metadata and OAuth foundation for Google-native documents." actions={<StatusBadge>Not configured</StatusBadge>} /><main className="mt-7 grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]"><section className="grid gap-4 sm:grid-cols-3">{cards.map(([title, detail]) => <article className="rounded-xl border border-neutral-800 bg-neutral-950 p-5" key={title}><h2 className="font-semibold">{title}</h2><p className="mt-2 text-sm text-neutral-400">{detail}</p></article>)}</section><aside className="rounded-xl border border-amber-900 bg-amber-950/20 p-5"><h2 className="font-semibold text-amber-200">Configuration required</h2><p className="mt-2 text-sm text-neutral-300">No Google credentials are configured. Connect and creation actions will appear after an administrator completes reviewed OAuth setup.</p><p className="mt-4 text-xs text-neutral-500">Planned scope: drive.file where workable. Tokens remain in external secret storage; this screen never displays them.</p><Link className={`mt-5 ${secondaryButtonClass}`} href="/platform/connectors">Review connectors</Link></aside></main></AppShell></RouteGuard>;
}
