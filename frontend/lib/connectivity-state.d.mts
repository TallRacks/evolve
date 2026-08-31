export type ConnectivityStatus = "checking" | "online" | "degraded" | "offline" | "reconnecting" | "restored";
export type ConnectivityEvent =
  | { type: "browser-offline" }
  | { type: "browser-online" }
  | { type: "probe-network-retry" }
  | { type: "probe-network-failed" }
  | { type: "probe-response"; ok: boolean }
  | { type: "restored-timeout" };
export const CONNECTIVITY: Readonly<Record<ConnectivityStatus, ConnectivityStatus>>;
export function connectivityTransition(current: ConnectivityStatus, event: ConnectivityEvent): ConnectivityStatus;
export function connectivityMessage(status: ConnectivityStatus): { tone: string; label: string; detail: string } | null;
