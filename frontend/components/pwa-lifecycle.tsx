"use client";

import { CheckCircle2, RefreshCw, ServerCrash, WifiOff, X } from "lucide-react";
import { useEffect, useReducer, useState } from "react";
import {
  CONNECTIVITY,
  connectivityMessage,
  connectivityTransition,
  type ConnectivityStatus,
} from "@/lib/connectivity-state.mjs";

const HEALTH_CHECK_INTERVAL = 30_000;
const HEALTH_CHECK_TIMEOUT = 5_000;
const RETRY_DELAY = 1_200;

export function PwaLifecycle() {
  const [connectivity, dispatch] = useReducer(
    connectivityTransition,
    CONNECTIVITY.checking as ConnectivityStatus,
  );
  const [updateReady, setUpdateReady] = useState<ServiceWorker | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const controllers = new Set<AbortController>();
    const delay = (milliseconds: number) =>
      new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds));

    async function verifyReachability() {
      for (let attempt = 1; attempt <= 2; attempt += 1) {
        const controller = new AbortController();
        controllers.add(controller);
        const timeout = window.setTimeout(() => controller.abort(), HEALTH_CHECK_TIMEOUT);
        try {
          const response = await fetch(`/api/health/?connectivity=${Date.now()}`, {
            cache: "no-store",
            credentials: "same-origin",
            headers: { Accept: "application/json" },
            signal: controller.signal,
          });
          if (!cancelled) dispatch({ type: "probe-response", ok: response.ok });
          return;
        } catch {
          if (cancelled) return;
          if (attempt < 2) {
            dispatch({ type: "probe-network-retry" });
            await delay(RETRY_DELAY);
          } else {
            dispatch({ type: "probe-network-failed" });
          }
        } finally {
          window.clearTimeout(timeout);
          controllers.delete(controller);
        }
      }
    }

    const browserOffline = () => {
      dispatch({ type: "browser-offline" });
      void verifyReachability();
    };
    const browserOnline = () => {
      dispatch({ type: "browser-online" });
      void verifyReachability();
    };
    window.addEventListener("offline", browserOffline);
    window.addEventListener("online", browserOnline);
    void verifyReachability();
    const interval = window.setInterval(() => void verifyReachability(), HEALTH_CHECK_INTERVAL);

    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      void navigator.serviceWorker.register("/sw.js").then((registration) => {
        if (registration.waiting) setUpdateReady(registration.waiting);
        registration.addEventListener("updatefound", () => {
          const worker = registration.installing;
          worker?.addEventListener("statechange", () => {
            if (worker.state === "installed" && navigator.serviceWorker.controller) setUpdateReady(worker);
          });
        });
      }).catch(() => undefined);
      const refreshed = () => window.location.reload();
      navigator.serviceWorker.addEventListener("controllerchange", refreshed, { once: true });
      return () => {
        cancelled = true;
        controllers.forEach((controller) => controller.abort());
        window.clearInterval(interval);
        window.removeEventListener("online", browserOnline);
        window.removeEventListener("offline", browserOffline);
        navigator.serviceWorker.removeEventListener("controllerchange", refreshed);
      };
    }
    return () => {
      cancelled = true;
      controllers.forEach((controller) => controller.abort());
      window.clearInterval(interval);
      window.removeEventListener("online", browserOnline);
      window.removeEventListener("offline", browserOffline);
    };
  }, []);

  useEffect(() => {
    if (connectivity !== CONNECTIVITY.restored) return;
    const timeout = window.setTimeout(() => dispatch({ type: "restored-timeout" }), 2_500);
    return () => window.clearTimeout(timeout);
  }, [connectivity]);

  const status = connectivityMessage(connectivity);
  const StatusIcon = connectivity === CONNECTIVITY.offline
    ? WifiOff
    : connectivity === CONNECTIVITY.degraded
      ? ServerCrash
      : connectivity === CONNECTIVITY.restored
        ? CheckCircle2
        : RefreshCw;

  return (
    <>
      {status && (
        <div
          className={`pwa-status fixed inset-x-0 top-0 z-[70] flex min-h-11 items-center justify-center gap-3 px-4 py-2 text-center text-sm font-semibold ${status.tone === "offline" ? "bg-amber-400 text-neutral-950" : status.tone === "restored" ? "bg-emerald-800 text-emerald-50" : "border-b border-neutral-700 bg-neutral-900 text-neutral-100"}`}
          data-connectivity={connectivity}
          role="status"
        >
          <StatusIcon aria-hidden="true" className={connectivity === CONNECTIVITY.reconnecting ? "animate-spin" : ""} size={16} />
          <span><strong>{status.label}</strong> <span className="font-normal">{status.detail}</span></span>
        </div>
      )}
      {updateReady && !dismissed && (
        <div className="pwa-status fixed inset-x-0 bottom-0 z-[70] flex min-h-11 items-center justify-center gap-3 border-t border-neutral-700 bg-neutral-900 px-4 py-2 text-sm text-neutral-100" role="status">
          <button className="inline-flex items-center gap-2 font-semibold text-amber-300" onClick={() => updateReady.postMessage({ type: "SKIP_WAITING" })}>
            <RefreshCw aria-hidden="true" size={16} /> A new version of Evolve is available. Refresh
          </button>
          <button aria-label="Dismiss update" className="grid size-8 place-items-center" onClick={() => setDismissed(true)}>
            <X aria-hidden="true" size={16} />
          </button>
        </div>
      )}
    </>
  );
}
