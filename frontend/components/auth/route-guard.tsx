"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/auth-provider";
import { canAccessPortal, type Portal } from "@/lib/auth/access";

export function RouteGuard({ portal, children }: { portal: Portal; children: React.ReactNode }) {
  const router = useRouter();
  const { session, loading, activeOrganizationId } = useAuth();
  const allowed = session ? canAccessPortal(session, portal, activeOrganizationId) : false;

  useEffect(() => {
    if (!loading && !session) router.replace("/login");
  }, [loading, router, session]);

  if (loading || (!session && !loading)) {
    return <StatusScreen title="Loading Evolve" detail="Checking your secure session." />;
  }
  if (!allowed) {
    return (
      <StatusScreen
        title="Access unavailable"
        detail="Your account does not have access to this portal or organization."
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
    <main className="grid min-h-screen place-items-center bg-neutral-950 px-6 text-neutral-100">
      <div className="max-w-md text-center">
        <p className="text-sm font-semibold uppercase text-amber-400">{forbidden ? "403" : "Evolve"}</p>
        <h1 className="mt-3 text-3xl font-semibold">{title}</h1>
        <p className="mt-4 text-neutral-400">{detail}</p>
      </div>
    </main>
  );
}
