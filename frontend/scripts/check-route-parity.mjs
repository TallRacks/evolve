import { existsSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const appRoot = new URL("../app/", import.meta.url).pathname;
const required = [
  "/dashboard", "/my-work", "/inbox", "/copilot", "/approvals",
  "/workspace/boards", "/workspace/automations", "/workspace/tasks",
  "/workspace/bookings", "/workspace/bookings/new", "/workspace/bookings/[id]/show-day", "/workspace/calendar",
  "/workspace/bookings/[id]/call-sheet", "/workspace/production", "/workspace/travel",
  "/workspace/artists", "/workspace/contacts", "/workspace/promoters", "/workspace/venues",
  "/workspace/music", "/workspace/music/releases", "/workspace/music/tracks", "/workspace/music/metadata", "/workspace/music/distribution", "/workspace/campaigns",
  "/workspace/rollouts/[id]", "/workspace/contracts", "/workspace/documents",
  "/workspace/finance", "/workspace/rights", "/workspace/royalties", "/workspace/reports",
  "/platform", "/platform/ai", "/platform/channels", "/platform/google-workspace", "/platform/connectors",
  "/platform/email-delivery", "/platform/storage", "/profile", "/profile/channels",
  "/profile/security", "/notifications", "/login", "/offline"
];

function routeToPath(route) {
  return join(appRoot, route.replace(/^\//, "").replace(/\[([^\]]+)\]/g, "[$1]"), "page.tsx");
}
const missing = required.filter((route) => !existsSync(routeToPath(route)));
if (missing.length) throw new Error(`Missing canonical routes: ${missing.join(", ")}`);
let pageCount = 0;
function walk(dir) { for (const name of readdirSync(dir)) { const path = join(dir, name); if (statSync(path).isDirectory()) walk(path); else if (name === "page.tsx" || name === "route.ts") pageCount += 1; } }
walk(appRoot);
console.log(`route parity OK (${pageCount} page/route files, ${required.length} canonical checks)`);
