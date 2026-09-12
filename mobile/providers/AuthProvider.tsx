import { PropsWithChildren, createContext, useContext, useEffect, useMemo, useState } from "react";
import { clearCredentials, hasStoredCredentials, signIn, signOut } from "../lib/auth";

type AuthContextValue = { ready: boolean; authenticated: boolean; login: (email: string, password: string) => Promise<void>; logout: () => Promise<void> };
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [ready, setReady] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  useEffect(() => { hasStoredCredentials().then(setAuthenticated).finally(() => setReady(true)); }, []);
  const value = useMemo(() => ({ ready, authenticated, login: async (email: string, password: string) => { await signIn(email, password); setAuthenticated(true); }, logout: async () => { await signOut(); setAuthenticated(false); }, }), [ready, authenticated]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error("useAuth must be used inside AuthProvider"); return value; }

export async function resetNativeCredentials() { await clearCredentials(); }
