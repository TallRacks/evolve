import * as SecureStore from "expo-secure-store";
import { API_BASE_URL, ApiError } from "./api";

const ACCESS_KEY = "evolve.mobile.access";
const REFRESH_KEY = "evolve.mobile.refresh";

type TokenResponse = { tokens: { access: string; refresh: string; access_expires_in: number; refresh_expires_in: number } };

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers: { Accept: "application/json", "Content-Type": "application/json", ...init.headers } });
  if (response.ok) return (await response.json()) as T;
  throw new ApiError(response.status === 401 ? "auth" : response.status >= 500 ? "server" : "validation", "The Evolve service could not complete that request.", response.status);
}

export async function signIn(email: string, password: string): Promise<void> {
  const result = await request<TokenResponse>("/mobile/auth/login/", { method: "POST", body: JSON.stringify({ email, password, platform: "native" }) });
  await SecureStore.setItemAsync(ACCESS_KEY, result.tokens.access);
  await SecureStore.setItemAsync(REFRESH_KEY, result.tokens.refresh);
}

export async function signOut(): Promise<void> {
  const access = await SecureStore.getItemAsync(ACCESS_KEY);
  if (access) await fetch(`${API_BASE_URL}/auth/mobile/auth/logout/`, { method: "POST", headers: { Authorization: `Bearer ${access}` } }).catch(() => undefined);
  await clearCredentials();
}

export async function clearCredentials(): Promise<void> {
  await SecureStore.deleteItemAsync(ACCESS_KEY);
  await SecureStore.deleteItemAsync(REFRESH_KEY);
}

async function refresh(): Promise<string> {
  const refreshToken = await SecureStore.getItemAsync(REFRESH_KEY);
  if (!refreshToken) throw new ApiError("auth", "Your mobile session has expired.", 401);
  const result = await request<TokenResponse>("/mobile/auth/refresh/", { method: "POST", body: JSON.stringify({ refresh: refreshToken }) });
  await SecureStore.setItemAsync(ACCESS_KEY, result.tokens.access);
  await SecureStore.setItemAsync(REFRESH_KEY, result.tokens.refresh);
  return result.tokens.access;
}

export async function authenticatedRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  let access = await SecureStore.getItemAsync(ACCESS_KEY);
  if (!access) access = await refresh();
  const send = () => fetch(`${API_BASE_URL}${path}`, { ...init, headers: { Accept: "application/json", "Content-Type": "application/json", Authorization: `Bearer ${access}`, ...init.headers } });
  let response = await send();
  if (response.status === 401) {
    try {
      access = await refresh();
    } catch (error) {
      await clearCredentials();
      throw error;
    }
    response = await send();
  }
  if (!response.ok) throw new ApiError(response.status === 401 ? "auth" : response.status === 403 ? "permission" : response.status >= 500 ? "server" : "validation", "The Evolve service could not complete that request.", response.status);
  return (await response.json()) as T;
}

export async function hasStoredCredentials(): Promise<boolean> {
  return Boolean(await SecureStore.getItemAsync(REFRESH_KEY));
}
