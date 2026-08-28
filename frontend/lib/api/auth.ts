import type { SessionBootstrap } from "@/lib/auth/types";

const CSRF_COOKIE = "csrftoken";

function cookieValue(name: string): string | null {
  const prefix = `${name}=`;
  const cookie = document.cookie.split("; ").find((item) => item.startsWith(prefix));
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
}

async function bootstrapCsrf(): Promise<string> {
  const response = await fetch("/api/auth/csrf/", {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error("Unable to initialize a secure session.");
  }
  const token = cookieValue(CSRF_COOKIE);
  if (!token) {
    throw new Error("Unable to initialize a secure session.");
  }
  return token;
}

export async function fetchCurrentUser(): Promise<SessionBootstrap | null> {
  const response = await fetch("/api/auth/me/", {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (response.status === 401) {
    const data = (await response.json().catch(() => null)) as { code?: string } | null;
    if (data?.code === "reauthentication_required" && !window.location.pathname.startsWith("/reauthenticate")) {
      globalThis.location.replace(`/reauthenticate?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
    }
    return null;
  }
  if (response.status === 403) {
    return null;
  }
  if (!response.ok) {
    throw new Error("Unable to load your session.");
  }
  return response.json() as Promise<SessionBootstrap>;
}

export async function login(email: string, password: string): Promise<SessionBootstrap> {
  const csrfToken = await bootstrapCsrf();
  const response = await fetch("/api/auth/login/", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken,
    },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    if (response.status === 400) {
      throw new Error("Invalid email or password.");
    }
    throw new Error("Sign in is unavailable. Please try again.");
  }
  return response.json() as Promise<SessionBootstrap>;
}

export async function logout(): Promise<void> {
  const csrfToken = await bootstrapCsrf();
  const response = await fetch("/api/auth/logout/", {
    method: "POST",
    credentials: "same-origin",
    headers: { Accept: "application/json", "X-CSRFToken": csrfToken },
  });
  if (!response.ok) {
    throw new Error("Unable to sign out.");
  }
}
