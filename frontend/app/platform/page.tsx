import { AppShell } from "@/components/app-shell";
import { RouteGuard } from "@/components/auth/route-guard";

export default function PlatformPage() {
  return (
    <RouteGuard portal="platform">
      <AppShell
        eyebrow="Platform portal"
        title="Platform Administration"
        description="Platform-wide access for Evolve operations. Internal Django administration remains at /admin/."
      />
    </RouteGuard>
  );
}
