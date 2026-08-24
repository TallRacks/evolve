const CSRF_COOKIE = "csrftoken";

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

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = init.method?.toUpperCase() ?? "GET";
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");
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
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(
      Array.isArray(detail)
        ? detail.join(" ")
        : typeof detail === "string"
          ? detail
          : "The request could not be completed.",
    );
  }
  return data as T;
}
