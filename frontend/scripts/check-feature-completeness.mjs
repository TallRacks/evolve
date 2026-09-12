import { readFileSync } from "node:fs";

const document = readFileSync(new URL("../../docs/feature-completeness.md", import.meta.url), "utf8");
const domains = [
  "Dashboard", "Artists", "Bookings", "Production", "Call Sheets", "Travel", "Promoters", "Venues", "Contacts",
  "Releases", "Tracks", "Works", "Campaigns", "Rollouts", "Calendar", "Tasks", "Notifications", "Activity",
  "Documents", "Contracts", "Finance", "Invoices", "Payments", "Rights", "Royalties", "Reports", "Team", "Invitations",
  "Organization", "Branding", "Domains", "Developer", "Email", "Storage", "AI", "Channels", "My Work", "Inbox",
  "Approvals", "Boards", "Automations", "Music Workspace", "Workspaces",
];
const rows = document.split("\n").filter((line) => line.startsWith("| "));
const missing = domains.filter((domain) => !rows.some((line) => line.split("|")[1]?.trim().split(/\s*\/\s*/).includes(domain)));
if (missing.length) throw new Error(`Feature completeness document is missing: ${missing.join(", ")}`);
for (const column of ["LIST", "CREATE", "DETAIL", "EDIT", "LIFECYCLE", "RELATED ACTIONS", "SEARCH/FILTER", "MOBILE WEB", "PWA", "NATIVE API READY"]) {
  if (!document.split("\n").find((line) => line.startsWith("|") && line.toUpperCase().includes(column === "SEARCH/FILTER" ? "SEARCH/FILTER" : `| ${column} |`))) throw new Error(`Feature completeness document is missing column: ${column}`);
}
console.log(`feature completeness OK (${domains.length} domains)`);
