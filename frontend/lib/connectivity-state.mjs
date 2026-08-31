export const CONNECTIVITY = Object.freeze({
  checking: "checking",
  online: "online",
  degraded: "degraded",
  offline: "offline",
  reconnecting: "reconnecting",
  restored: "restored",
});

export function connectivityTransition(current, event) {
  switch (event.type) {
    case "browser-offline":
      return CONNECTIVITY.checking;
    case "browser-online":
      return CONNECTIVITY.reconnecting;
    case "probe-network-retry":
      return current === CONNECTIVITY.offline || current === CONNECTIVITY.reconnecting
        ? CONNECTIVITY.reconnecting
        : CONNECTIVITY.checking;
    case "probe-network-failed":
      return CONNECTIVITY.offline;
    case "probe-response":
      if (!event.ok) return CONNECTIVITY.degraded;
      return current === CONNECTIVITY.offline || current === CONNECTIVITY.reconnecting
        ? CONNECTIVITY.restored
        : CONNECTIVITY.online;
    case "restored-timeout":
      return CONNECTIVITY.online;
    default:
      return current;
  }
}

export function connectivityMessage(status) {
  if (status === CONNECTIVITY.offline) {
    return { tone: "offline", label: "Offline", detail: "Some live actions are unavailable until Evolve reconnects." };
  }
  if (status === CONNECTIVITY.reconnecting) {
    return { tone: "checking", label: "Reconnecting...", detail: "Checking the secure Evolve service." };
  }
  if (status === CONNECTIVITY.degraded) {
    return { tone: "degraded", label: "Service issue", detail: "Evolve is reachable, but a service check needs attention." };
  }
  if (status === CONNECTIVITY.restored) {
    return { tone: "restored", label: "Back online", detail: "Live actions are available again." };
  }
  return null;
}
