import { AppShell } from "@/components/app-shell";
import { RouteGuard } from "@/components/auth/route-guard";

export default function DashboardPage() {
  return (
    <RouteGuard portal="dashboard">
      <AppShell
        eyebrow="Authenticated home"
        title="Evolve v2"
        description="Your secure entry point for Evolve management and operations."
      />
    </RouteGuard>
  );
}
