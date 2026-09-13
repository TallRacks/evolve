"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { fetchCurrentUser, login as apiLogin, logout as apiLogout } from "@/lib/api/auth";
import type { SessionBootstrap } from "@/lib/auth/types";

const ORGANIZATION_KEY = "evolve.activeOrganizationId";
const WORKSPACE_KEY = "evolve.activeWorkspaceId";

interface AuthContextValue {
  session: SessionBootstrap | null;
  loading: boolean;
  activeOrganizationId: string | null;
  refresh: () => Promise<void>;
  login: (email: string, password: string) => Promise<SessionBootstrap>;
  logout: () => Promise<void>;
  selectOrganization: (organizationId: string | null) => void;
  activeWorkspaceId: string | null;
  selectWorkspace: (workspaceId: string | null) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function availableOrganizations(session: SessionBootstrap) {
  return session.user.is_superuser
    ? session.organizations
    : session.memberships.map((item) => item.organization);
}

function validOrganization(session: SessionBootstrap, candidate: string | null): string | null {
  const organizations = availableOrganizations(session);
  if (session.user.is_superuser && (!candidate || candidate === "platform")) return null;
  if (candidate && organizations.some((item) => item.id === candidate)) return candidate;
  return organizations[0]?.id ?? null;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<SessionBootstrap | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeOrganizationId, setActiveOrganizationId] = useState<string | null>(null);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(null);

  const applySession = useCallback((next: SessionBootstrap | null) => {
    setSession(next);
    if (!next) {
      setActiveOrganizationId(null);
      setActiveWorkspaceId(null);
      sessionStorage.removeItem(ORGANIZATION_KEY);
      sessionStorage.removeItem(WORKSPACE_KEY);
      return;
    }
    const selected = validOrganization(next, sessionStorage.getItem(ORGANIZATION_KEY));
    setActiveOrganizationId(selected);
    const storedWorkspace = sessionStorage.getItem(WORKSPACE_KEY);
    setActiveWorkspaceId(selected ? storedWorkspace : null);
    if (selected) sessionStorage.setItem(ORGANIZATION_KEY, selected);
    else if (next.user.is_superuser) sessionStorage.setItem(ORGANIZATION_KEY, "platform");
    else sessionStorage.removeItem(ORGANIZATION_KEY);
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      applySession(await fetchCurrentUser());
    } finally {
      setLoading(false);
    }
  }, [applySession]);

  useEffect(() => {
    let cancelled = false;
    fetchCurrentUser()
      .then((next) => {
        if (!cancelled) applySession(next);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [applySession]);

  const login = useCallback(
    async (email: string, password: string) => {
      const next = await apiLogin(email, password);
      applySession(next);
      return next;
    },
    [applySession],
  );

  const logout = useCallback(async () => {
    await apiLogout();
    applySession(null);
  }, [applySession]);

  const selectOrganization = useCallback(
    (organizationId: string | null) => {
      if (!session) return;
      if (organizationId === null && session.user.is_superuser) {
        sessionStorage.setItem(ORGANIZATION_KEY, "platform");
        setActiveOrganizationId(null);
        setActiveWorkspaceId(null);
        sessionStorage.removeItem(WORKSPACE_KEY);
        return;
      }
      if (!organizationId || !availableOrganizations(session).some((item) => item.id === organizationId)) return;
      sessionStorage.setItem(ORGANIZATION_KEY, organizationId);
      setActiveOrganizationId(organizationId);
      setActiveWorkspaceId(null);
      sessionStorage.removeItem(WORKSPACE_KEY);
    },
    [session],
  );

  const selectWorkspace = useCallback((workspaceId: string | null) => {
    if (!workspaceId) { sessionStorage.removeItem(WORKSPACE_KEY); setActiveWorkspaceId(null); return; }
    sessionStorage.setItem(WORKSPACE_KEY, workspaceId);
    setActiveWorkspaceId(workspaceId);
  }, []);

  const value = useMemo(
    () => ({ session, loading, activeOrganizationId, refresh, login, logout, selectOrganization, activeWorkspaceId, selectWorkspace }),
    [session, loading, activeOrganizationId, refresh, login, logout, selectOrganization, activeWorkspaceId, selectWorkspace],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
