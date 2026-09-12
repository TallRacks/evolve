export type ApiErrorKind = "validation" | "auth" | "permission" | "not_found" | "conflict" | "server" | "network";

export class ApiError extends Error {
  constructor(public readonly kind: ApiErrorKind, message: string, public readonly status?: number) {
    super(message);
  }
}

export const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";
export const isDevelopmentMock = process.env.EXPO_PUBLIC_MOCK_SESSION === "true" && __DEV__;

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  if (isDevelopmentMock) throw new ApiError("network", "Development mock adapter has no remote data.");
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers: { Accept: "application/json", ...init?.headers } });
    if (response.ok) return (await response.json()) as T;
    const kind: ApiErrorKind = response.status === 401 ? "auth" : response.status === 403 ? "permission" : response.status === 404 ? "not_found" : response.status === 409 ? "conflict" : response.status >= 500 ? "server" : "validation";
    throw new ApiError(kind, "The Evolve service could not complete that request.", response.status);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError("network", "Evolve is offline. Check your connection and try again.");
  }
}
