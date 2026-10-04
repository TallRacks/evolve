"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, LogIn } from "lucide-react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/components/auth/auth-provider";
import { canAccessPortal, type Portal } from "@/lib/auth/access";
import { apiRequest } from "@/lib/api/client";

export function RouteGuard({ portal, children }: { portal: Portal; children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { session, loading, activeOrganizationId, selectOrganization } = useAuth();
  const [featureLoading, setFeatureLoading] = useState(false);
  const [featureAllowed, setFeatureAllowed] = useState(true);
  const needsSuperuserOrganization = Boolean(
    session?.user.is_superuser &&
      portal === "workspace" &&
      !activeOrganizationId &&
      session.organizations.length > 0,
  );
  const featureKey = !session?.user.is_superuser && portal === "workspace" ? (
    pathname === "/workspace/activity" ? "activity" :
    pathname === "/workspace/reports" || pathname.startsWith("/workspace/reports/") ? "reports" :
    pathname === "/workspace/boards" ? "boards" :
    pathname === "/workspace" || pathname.startsWith("/workspace/office") ? "office" :
    pathname.startsWith("/workspace/settings/trackers") ? "booking-tracker" :
    pathname.startsWith("/workspace/settings/booking-options") ? "booking-options" :
    pathname === "/inbox" ? "mailroom" :
    pathname.startsWith("/workspace/signing") ? "signing" :
    pathname.startsWith("/workspace/settings/templates") ? "template-editor" : undefined
  ) : undefined;
  const allowed = session ? (canAccessPortal(session, portal, activeOrganizationId) || needsSuperuserOrganization) && featureAllowed : false;

  useEffect(() => {
    if (!featureKey || !activeOrganizationId || !session) {
      queueMicrotask(() => { setFeatureAllowed(true); setFeatureLoading(false); });
      return;
    }
    queueMicrotask(() => setFeatureLoading(true));
    void apiRequest<Array<{ key: string; is_enabled: boolean }>>(`/api/organizations/${activeOrganizationId}/features/`)
      .then((items) => setFeatureAllowed(items.find((item) => item.key === featureKey)?.is_enabled !== false))
      .catch(() => setFeatureAllowed(false))
      .finally(() => setFeatureLoading(false));
  }, [activeOrganizationId, featureKey, session]);

  useEffect(() => {
    if (!loading && !session) router.replace("/login");
  }, [loading, router, session]);

  useEffect(() => {
    if (needsSuperuserOrganization && session) {
      selectOrganization(session.organizations[0].id);
    }
  }, [needsSuperuserOrganization, selectOrganization, session]);

  if (loading || featureLoading || (!session && !loading)) {
    return <StatusScreen title="Loading Evolve" detail="Checking your secure session." />;
  }
  if (needsSuperuserOrganization) {
    return <StatusScreen title="Opening workspace" detail="Selecting an organization for your superuser session." />;
  }
  if (!allowed) {
    return (
      <StatusScreen
        title="Access unavailable"
        detail={featureKey && !featureAllowed ? "This workspace feature is currently disabled for your account." : "Your account does not have access to this portal or organization."}
        forbidden
      />
    );
  }
  return children;
}

function StatusScreen({
  title,
  detail,
  forbidden = false,
}: {
  title: string;
  detail: string;
  forbidden?: boolean;
}) {
  return (
    <main className="grid min-h-dvh place-items-center bg-[var(--background)] px-6 py-12 text-[var(--text-primary)]">
      <section className="evolve-panel w-full max-w-md p-8 text-center shadow-sm">
        <p className="evolve-eyebrow text-xs font-semibold uppercase">{forbidden ? "Access" : "Evolve workspace"}</p>
        <h1 className="evolve-display mt-3 text-3xl font-semibold">{title}</h1>
        <p className="mt-4 text-sm leading-6 text-[var(--text-muted)]">{detail}</p>
        {forbidden ? <p className="mt-4 text-xs leading-5 text-[var(--text-muted)]">Platform pages require an active platform superuser session. If you recently changed access, sign out and sign in again.</p> : null}
        <div className="mt-7 flex flex-wrap justify-center gap-3">
          <Link className="inline-flex min-h-10 items-center gap-2 rounded-[var(--radius)] bg-[var(--accent)] px-4 text-sm font-semibold text-[var(--accent-ink)]" href="/dashboard"><ArrowLeft size={16} /> Dashboard</Link>
          {forbidden && <Link className="inline-flex min-h-10 items-center gap-2 rounded-[var(--radius)] border border-[var(--border)] px-4 text-sm font-semibold" href="/login"><LogIn size={16} /> Sign in again</Link>}
        </div>
      </section>
    </main>
  );
}
