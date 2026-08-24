import { AppShell } from "@/components/app-shell";
import { RouteGuard } from "@/components/auth/route-guard";

export default function WorkspacePage() {
  return (
    <RouteGuard portal="workspace">
      <AppShell
        eyebrow="Organisation portal"
        title="Organisation Workspace"
        description="The authenticated organisation context for future management operations."
        organizationScoped
      />
    </RouteGuard>
  );
}
