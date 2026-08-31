const CSRF_COOKIE = "csrftoken";

type ErrorPayload = Record<string, unknown> | null;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly fields: Record<string, string[]>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function cookieValue(name: string): string | null {
  const prefix = `${name}=`;
  const cookie = document.cookie.split("; ").find((item) => item.startsWith(prefix));
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
}

async function csrfToken(): Promise<string> {
  await fetch("/api/auth/csrf/", { credentials: "same-origin" });
  const token = cookieValue(CSRF_COOKIE);
  if (!token) throw new Error("Unable to initialize a secure request.");
  return token;
}

function messages(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(messages);
  return [];
}

function responseError(status: number, data: ErrorPayload): ApiError {
  const fields: Record<string, string[]> = {};
  if (data) {
    for (const [field, value] of Object.entries(data)) {
      if (field !== "detail" && field !== "non_field_errors") {
        const fieldMessages = messages(value);
        if (fieldMessages.length) fields[field] = fieldMessages;
      }
    }
  }
  const detail = messages(data?.detail)[0] ?? messages(data?.non_field_errors)[0];
  const fallback: Record<number, string> = {
    400: "Review the highlighted values and try again.",
    401: "Your session has expired. Sign in again.",
    403: "You do not have permission to perform this action.",
    404: "The requested record was not found.",
    409: "This record changed. Reload it before trying again.",
    422: "The submitted values could not be processed.",
    500: "The service could not complete the request. Try again safely.",
  };
  return new ApiError(detail ?? Object.values(fields).flat()[0] ?? fallback[status] ?? "The request could not be completed.", status, fields);
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = init.method?.toUpperCase() ?? "GET";
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    headers.set("X-CSRFToken", await csrfToken());
  }
  const response = await fetch(path, {
    ...init,
    headers,
    credentials: "same-origin",
    cache: method === "GET" ? "no-store" : init.cache,
  });
  if (response.status === 204) return undefined as T;
  const data = (await response.json().catch(() => null)) as ErrorPayload;
  if (
    response.status === 401 &&
    data?.code === "reauthentication_required" &&
    typeof window !== "undefined" &&
    !window.location.pathname.startsWith("/reauthenticate")
  ) {
    globalThis.location.replace(`/reauthenticate?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
  }
  if (!response.ok) throw responseError(response.status, data);
  return data as T;
}
