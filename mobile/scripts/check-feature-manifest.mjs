/* global URL, console */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
const root = new URL("../app/", import.meta.url).pathname;
const manifest = JSON.parse(readFileSync(new URL("../feature-manifest.json", import.meta.url)));
const files = [];
function walk(dir) { for (const name of readdirSync(dir)) { const path = join(dir, name); if (statSync(path).isDirectory()) walk(path); else if (/\.tsx$/.test(name)) files.push(path); } }
walk(root);
const required = new Set(["/", "/my-work", "/inbox", "/tasks", "/artists", "/bookings", "/calendar", "/notifications", "/copilot", "/profile"]);
for (const entry of manifest) if (!required.has(entry.route)) throw new Error(`Unexpected manifest route: ${entry.route}`);
if (manifest.length !== required.size || files.length < 15) throw new Error("Native feature manifest or initial screen set is incomplete");
console.log(`mobile feature manifest OK (${manifest.length} primary routes, ${files.length} screens)`);
