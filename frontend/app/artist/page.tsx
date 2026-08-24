import { AppShell } from "@/components/app-shell";
import { RouteGuard } from "@/components/auth/route-guard";

export default function ArtistPage() {
  return (
    <RouteGuard portal="artist">
      <AppShell
        eyebrow="Artist-facing portal"
        title="Artist Portal"
        description="The authenticated artist-facing boundary. Artist remains separate from User in the domain model."
        organizationScoped
      />
    </RouteGuard>
  );
}
