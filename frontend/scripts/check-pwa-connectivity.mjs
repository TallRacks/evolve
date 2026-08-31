import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { CONNECTIVITY, connectivityMessage, connectivityTransition } from "../lib/connectivity-state.mjs";

const transition = (state, type, extra = {}) => connectivityTransition(state, { type, ...extra });

test("initial checking state has no offline banner", () => {
  assert.equal(connectivityMessage(CONNECTIVITY.checking), null);
});
test("browser offline is advisory until reachability retries fail", () => {
  assert.equal(transition(CONNECTIVITY.online, "browser-offline"), CONNECTIVITY.checking);
  assert.equal(transition(CONNECTIVITY.checking, "probe-network-retry"), CONNECTIVITY.checking);
  assert.equal(transition(CONNECTIVITY.checking, "probe-network-failed"), CONNECTIVITY.offline);
});
test("online event reconnects and a successful probe restores service", () => {
  assert.equal(transition(CONNECTIVITY.offline, "browser-online"), CONNECTIVITY.reconnecting);
  assert.equal(transition(CONNECTIVITY.reconnecting, "probe-response", { ok: true }), CONNECTIVITY.restored);
  assert.equal(transition(CONNECTIVITY.restored, "restored-timeout"), CONNECTIVITY.online);
  assert.equal(connectivityMessage(CONNECTIVITY.online), null);
});
test("successful initial health check is online", () => {
  assert.equal(transition(CONNECTIVITY.checking, "probe-response", { ok: true }), CONNECTIVITY.online);
});
test("HTTP errors prove reachability and never become offline", () => {
  for (const status of [401, 403, 500]) {
    const state = transition(CONNECTIVITY.checking, "probe-response", { ok: false, status });
    assert.equal(state, CONNECTIVITY.degraded);
    assert.notEqual(state, CONNECTIVITY.offline);
  }
});
test("offline and reconnect messages are explicit", () => {
  assert.equal(connectivityMessage(CONNECTIVITY.offline)?.label, "Offline");
  assert.equal(connectivityMessage(CONNECTIVITY.reconnecting)?.label, "Reconnecting...");
  assert.equal(connectivityMessage(CONNECTIVITY.restored)?.label, "Back online");
});
test("service worker excludes private and authenticated data", () => {
  const root = join(dirname(fileURLToPath(import.meta.url)), "..");
  const worker = readFileSync(join(root, "public", "sw.js"), "utf8");
  assert.match(worker, /url\.pathname\.startsWith\("\/api\/"\)/);
  assert.match(worker, /url\.pathname\.startsWith\("\/admin\/"\)/);
  assert.match(worker, /request\.mode === "navigate"/);
  assert.match(worker, /fetch\(request\)\.catch\(\(\) => caches\.match\("\/offline"\)\)/);
  assert.doesNotMatch(worker, /cache\.put\(request,[\s\S]*request\.mode === "navigate"/);
  assert.doesNotMatch(worker, /localStorage|sessionStorage|Authorization|csrf/i);
});
