import type { SessionBootstrap } from "@/lib/auth/types";

export type Portal = "dashboard" | "workspace" | "artist" | "platform";

export function hasOrganizationPermission(
  session: SessionBootstrap | null,
  organizationId: string | null,
  permission: string,
): boolean {
  if (!session || !organizationId) return false;
  if (session.user.is_superuser) {
    return session.organizations.some((organization) => organization.id === organizationId);
  }
  return !!session.memberships
    .find((membership) => membership.organization.id === organizationId)
    ?.permissions.includes(permission);
}

export function landingPath(session: SessionBootstrap): string {
  if (session.user.is_superuser) return "/dashboard";
  if (session.memberships.some((membership) => membership.permissions.includes("portal.artist"))) {
    return "/artist";
  }
  if (session.memberships.length > 0) return "/workspace";
  return "/dashboard";
}

export function canAccessPortal(
  session: SessionBootstrap,
  portal: Portal,
  organizationId: string | null,
): boolean {
  if (portal === "dashboard") return true;
  if (portal === "platform") return session.user.is_superuser;
  if (session.user.is_superuser) {
    return (
      portal === "workspace" &&
      organizationId !== null &&
      session.organizations.some((organization) => organization.id === organizationId)
    );
  }
  const membership = session.memberships.find(
    (candidate) => candidate.organization.id === organizationId,
  );
  if (!membership) return false;
  if (portal === "workspace") return true;
  return membership.permissions.includes("portal.artist");
}
