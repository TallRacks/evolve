import { AppShell } from "@/components/app-shell";
import { RouteGuard } from "@/components/auth/route-guard";

export default function ArtistPage() {
  return (
    <RouteGuard portal="artist">
      <AppShell organizationScoped>
        <div className="border-b border-neutral-800 pb-7">
          <p className="text-xs font-semibold uppercase text-amber-400">Artist portal</p>
          <h1 className="mt-2 text-3xl font-semibold">Artist workspace</h1>
          <p className="mt-3 text-neutral-400">Artist operations remain intentionally deferred.</p>
        </div>
      </AppShell>
    </RouteGuard>
  );
}
