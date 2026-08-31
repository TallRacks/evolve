"use client";

import { RefreshCw, WifiOff, X } from "lucide-react";
import { useEffect, useState } from "react";

export function PwaLifecycle() {
  const [online, setOnline] = useState(() =>
    typeof navigator === "undefined" ? true : navigator.onLine,
  );
  const [updateReady, setUpdateReady] = useState<ServiceWorker | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const connected = () => setOnline(true);
    const disconnected = () => setOnline(false);
    window.addEventListener("online", connected);
    window.addEventListener("offline", disconnected);

    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      navigator.serviceWorker.register("/sw.js").then((registration) => {
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
        window.removeEventListener("online", connected);
        window.removeEventListener("offline", disconnected);
        navigator.serviceWorker.removeEventListener("controllerchange", refreshed);
      };
    }
    return () => {
      window.removeEventListener("online", connected);
      window.removeEventListener("offline", disconnected);
    };
  }, []);

  if (!online) {
    return (
      <div className="pwa-status fixed inset-x-0 top-0 z-[70] flex min-h-10 items-center justify-center gap-2 bg-amber-400 px-4 py-2 text-center text-sm font-semibold text-neutral-950" role="status">
        <WifiOff aria-hidden="true" size={16} /> Offline. Changes are unavailable until Evolve reconnects.
      </div>
    );
  }
  if (!updateReady || dismissed) return null;
  return (
    <div className="pwa-status fixed inset-x-0 top-0 z-[70] flex min-h-11 items-center justify-center gap-3 border-b border-neutral-700 bg-neutral-900 px-4 py-2 text-sm text-neutral-100" role="status">
      <button className="inline-flex items-center gap-2 font-semibold text-amber-300" onClick={() => updateReady.postMessage({ type: "SKIP_WAITING" })}>
        <RefreshCw aria-hidden="true" size={16} /> Update Evolve
      </button>
      <button aria-label="Dismiss update" className="grid size-8 place-items-center" onClick={() => setDismissed(true)}>
        <X aria-hidden="true" size={16} />
      </button>
    </div>
  );
}
