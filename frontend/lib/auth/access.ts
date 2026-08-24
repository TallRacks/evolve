import type { SessionBootstrap } from "@/lib/auth/types";

export type Portal = "dashboard" | "workspace" | "artist" | "platform";

export function landingPath(session: SessionBootstrap): string {
  if (session.user.is_superuser) return "/platform";
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
  if (session.user.is_superuser) return false;
  const membership = session.memberships.find(
    (candidate) => candidate.organization.id === organizationId,
  );
  if (!membership) return false;
  if (portal === "workspace") return true;
  return membership.permissions.includes("portal.artist");
}
