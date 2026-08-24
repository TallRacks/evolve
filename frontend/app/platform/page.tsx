import { PortalShell } from "@/components/portal-shell";

export default function PlatformPage() {
  return (
    <PortalShell
      eyebrow="Platform portal"
      title="Platform Administration"
      description="A future application workspace for platform-wide Evolve administration. Django's internal administration remains available at /admin/."
    />
  );
}
