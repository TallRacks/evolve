import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const manifest = JSON.parse(readFileSync(join(root, "action-manifest.json"), "utf8"));
const failures = [];

for (const action of manifest) {
  const routeFile = join(root, "app", action.route.replace(/^\//, ""), "page.tsx");
  const destinationFile = join(root, "app", action.destination.replace(/^\//, ""), "page.tsx");
  const sourceFile = join(root, action.source);
  if (!existsSync(routeFile)) failures.push(`${action.route}: route is missing`);
  if (!existsSync(destinationFile)) failures.push(`${action.route}: destination ${action.destination} is missing`);
  if (!existsSync(sourceFile)) {
    failures.push(`${action.route}: source ${action.source} is missing`);
    continue;
  }
  const source = readFileSync(sourceFile, "utf8");
  if (!source.includes(action.label)) failures.push(`${action.route}: label ${action.label} is not rendered`);
  if (!source.includes(action.permission)) failures.push(`${action.route}: permission ${action.permission} is not represented`);
}

const dashboard = readFileSync(join(root, "components/management-pages.tsx"), "utf8");
for (const label of ["New Booking", "New Artist", "New Contact", "New Production Advance", "New Travel Itinerary"]) {
  if (!dashboard.includes(label)) failures.push("/dashboard: quick action " + label + " is missing");
}
const access = readFileSync(join(root, "lib/auth/access.ts"), "utf8");
if (!access.includes("session.user.is_superuser")) failures.push("superuser workspace authorization representation is missing");
if (access.includes("is_staff")) failures.push("staff must not be treated as application authorization");

const detailContracts = [
  ["components/booking-pages.tsx", ["Edit Booking", "Generate Call Sheet"]],
  ["components/production-pages.tsx", ["Edit Advance", "Generate Call Sheet"]],
  ["components/call-sheet-pages.tsx", ["Preview", "Mark Ready", "Publish", "Print / Save PDF"]],
  ["components/contract-pages.tsx", ["Edit", "Submit for Review"]],
  ["components/finance-pages.tsx", ["New invoice", "Record payment"]],
  ["components/rights-pages.tsx", ["New Work", "New statement"]],
];
for (const [path, labels] of detailContracts) {
  const source = readFileSync(join(root, path), "utf8");
  for (const label of labels) {
    if (!source.includes(label)) failures.push(`${path}: critical action ${label} is missing`);
  }
}

for (const entry of readdirSync(join(root, "components"), { recursive: true })) {
  if (typeof entry !== "string" || !entry.endsWith(".tsx")) continue;
  const source = readFileSync(join(root, "components", entry), "utf8");
  if (/\b(?:event|e)\.currentTarget\.reset\(\)/.test(source)) {
    failures.push(`${entry}: retain the form element before awaiting a mutation`);
  }
}

if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
console.log(`Validated ${manifest.length} visible action contracts and dashboard authorization rules.`);
