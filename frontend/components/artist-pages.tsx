"use client";

import { hasOrganizationPermission } from "@/lib/auth/access";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { ArtistContractsSection } from "@/components/contract-pages";
import { ArtistMusicSection } from "@/components/music-pages";
import { ArtistCampaignSection } from "@/components/campaign-pages";
import {
  ArtistDocumentsSection,
  ArtistScheduleSection,
  EntityDocumentsSection,
} from "@/components/calendar-document-pages";
import { useAuth } from "@/components/auth/auth-provider";
import { RouteGuard } from "@/components/auth/route-guard";
import { apiRequest } from "@/lib/api/client";
import { confirmAction } from "@/components/ui/action-dialog";
import {
  Breadcrumbs,
  buttonClass,
  EmptyState,
  fieldClass,
  PageHeader,
  secondaryButtonClass,
  StatusBadge,
} from "@/components/ui/page";

interface Artist {
  id: string;
  organization: { id: string; name: string };
  stage_name: string;
  legal_name: string;
  slug: string;
  status: "active" | "inactive" | "archived";
  email: string;
  phone: string;
  biography: string;
  website: string;
  country: string;
  city: string;
  management_email: string;
  booking_email: string;
  profile_image_url: string;
  team_count: number;
  portal_user_count: number;
  primary_manager: { name: string; email: string } | null;
  created_at: string;
  updated_at: string;
  team?: Assignment[];
  portal_links?: PortalLink[];
  activity?: Activity[];
}
interface Assignment {
  id: string;
  member: {
    membership_id: string;
    user_id: string;
    email: string;
    name: string;
    organization_role: string;
    membership_active: boolean;
  };
  responsibility: string;
  is_primary: boolean;
  is_active: boolean;
  created_at: string;
}
interface PortalLink {
  id: string;
  user: { id: string; email: string; name: string };
  relationship: string;
  is_active: boolean;
}
interface Activity {
  id: string;
  action: string;
  description: string;
  actor: string | null;
  created_at: string;
}
interface Member {
  id: string;
  role: string;
  is_active: boolean;
  user: {
    id: string;
    email: string;
    first_name: string;
    last_name: string;
    is_active: boolean;
  };
}
interface PortalArtist {
  id: string;
  organization: string;
  stage_name: string;
  status: string;
  profile_image_url: string;
  biography: string;
  website: string;
  city: string;
  country: string;
  management_email: string;
  booking_email: string;
  team: {
    name: string;
    email: string;
    responsibility: string;
    is_primary: boolean;
  }[];
}
interface ArtistOverview {
  bookings: {
    id: string;
    reference: string;
    date: string;
    venue: string;
    promoter: string;
    status: string;
  }[];
  call_sheets: { id: string; title: string; date: string }[];
  releases: {
    id: string;
    title: string;
    date: string | null;
    status: string;
    artwork_url: string;
    upc_ean: string;
    public_url: string;
  }[];
  tracks: { id: string; title: string; status: string }[];
  campaigns: { id: string; name: string; status: string }[];
  documents: { id: string; title: string; type: string; content_type: string; original_filename: string; external_url: string }[];
  rights: {
    works: number;
    tracks_with_master_rights: number;
    incomplete_master_splits: number;
    incomplete_publishing_splits: number;
  };
}
interface ArtistToolkit {
  short_bio: string;
  long_bio: string;
  rate_card: string;
  stats_summary: string;
}

function Workspace({ children }: { children: React.ReactNode }) {
  return (
    <RouteGuard portal="workspace">
      <AppShell organizationScoped>{children}</AppShell>
    </RouteGuard>
  );
}
function Platform({ children }: { children: React.ReactNode }) {
  return (
    <RouteGuard portal="platform">
      <AppShell>{children}</AppShell>
    </RouteGuard>
  );
}
function Notice({
  message,
  error = false,
}: {
  message: string;
  error?: boolean;
}) {
  return message ? (
    <p
      className={`rounded-md border px-4 py-3 text-sm ${error ? "border-red-900 bg-red-950 text-red-200" : "border-emerald-900 bg-emerald-950 text-emerald-200"}`}
    >
      {message}
    </p>
  ) : null;
}
function Avatar({
  artist,
  large = false,
}: {
  artist: Pick<Artist, "stage_name" | "profile_image_url">;
  large?: boolean;
}) {
  return artist.profile_image_url ? (
    <Image
      unoptimized
      alt=""
      className={
        (large ? "size-28" : "size-12") + " shrink-0 rounded-md object-cover"
      }
      height={large ? 112 : 48}
      src={artist.profile_image_url}
      width={large ? 112 : 48}
    />
  ) : (
    <span
      className={`${large ? "size-28 text-3xl" : "size-12"} grid shrink-0 place-items-center rounded-md bg-neutral-800 font-semibold`}
    >
      {artist.stage_name.slice(0, 2).toUpperCase()}
    </span>
  );
}

function ArtistFields({ data }: { data?: Artist }) {
  const input = (name: keyof Artist, label: string, type = "text") => (
    <label className="text-sm text-neutral-400">
      {label}
      <input
        className={`mt-2 ${fieldClass}`}
        defaultValue={String(data?.[name] ?? "")}
        name={name}
        type={type}
      />
    </label>
  );
  return (
    <div className="grid gap-7">
      <section>
        <h2 className="font-semibold">Artist</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {input("stage_name", "Stage name")}
          {input("legal_name", "Legal name")}
          {input("slug", "URL slug")}
          <label className="text-sm text-neutral-400">
            Status
            <select
              className={`mt-2 ${fieldClass}`}
              defaultValue={data?.status ?? "active"}
              name="status"
            >
              {["active", "inactive", "archived"].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
        </div>
      </section>
      <section>
        <h2 className="font-semibold">Contact and location</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {input("email", "Email", "email")}
          {input("phone", "Phone")}
          {input("country", "Country")}
          {input("city", "City")}
        </div>
      </section>
      <section>
        <h2 className="font-semibold">Business</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {input("management_email", "Management email", "email")}
          {input("booking_email", "Booking email", "email")}
        </div>
      </section>
      <section>
        <h2 className="font-semibold">Profile</h2>
        <div className="mt-4 grid gap-4">
          {input("website", "Website", "url")}
          {input("profile_image_url", "Profile image URL", "url")}
          <label className="text-sm text-neutral-400">
            Biography
            <textarea
              className="mt-2 min-h-36 w-full rounded-md border border-neutral-700 bg-neutral-950 p-3 text-sm"
              defaultValue={data?.biography}
              name="biography"
            />
          </label>
        </div>
      </section>
    </div>
  );
}

export function ArtistDirectoryPage() {
  const { activeOrganizationId, session } = useAuth();
  const [data, setData] = useState<Artist[] | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const canManage = hasOrganizationPermission(session, activeOrganizationId, "artist.manage");
  useEffect(() => {
    if (!activeOrganizationId) return;
    void apiRequest<Artist[]>(
      `/api/artists/?organization_id=${activeOrganizationId}`,
    )
      .then(setData)
      .catch((caught) =>
        setError(
          caught instanceof Error ? caught.message : "Unable to load artists.",
        ),
      );
  }, [activeOrganizationId]);
  const filtered = useMemo(
    () =>
      (data ?? []).filter(
        (artist) =>
          (!query ||
            `${artist.stage_name} ${artist.legal_name} ${artist.city}`
              .toLowerCase()
              .includes(query.toLowerCase())) &&
          (!status || artist.status === status),
      ),
    [data, query, status],
  );
  return (
    <Workspace>
      <PageHeader
        eyebrow="Workspace"
        title="Artists"
        description="Managed artist profiles and assigned teams."
        actions={
          canManage ? (
            <Link className={buttonClass} href="/workspace/artists/new">
              Create artist
            </Link>
          ) : undefined
        }
      />
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <input
          className={fieldClass}
          placeholder="Search artists"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <select
          className={fieldClass}
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        >
          <option value="">All statuses</option>
          {["active", "inactive", "archived"].map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
      </div>
      <div className="mt-4">
        <Notice message={error} error />
      </div>
      {data === null ? (
        <p className="py-12 text-neutral-500">Loading artists...</p>
      ) : filtered.length === 0 ? (
        <div className="mt-7">
          <EmptyState
            title="No artists yet"
            detail={
              canManage
                ? "Create your first artist profile"
                : "No artist profiles are available."
            }
          />
        </div>
      ) : (
        <div className="mt-7 grid gap-3">
          {filtered.map((artist) => (
            <Link
              className="grid gap-4 evolve-panel p-5 hover:border-neutral-600 sm:grid-cols-[auto_1fr_auto_auto] sm:items-center"
              href={`/workspace/artists/${artist.id}`}
              key={artist.id}
            >
              <Avatar artist={artist} />
              <div>
                <p className="font-medium">{artist.stage_name}</p>
                <p className="text-sm text-neutral-500">
                  {[artist.city, artist.country].filter(Boolean).join(", ") ||
                    "Location not set"}
                </p>
              </div>
              <p className="text-sm text-neutral-400">
                {artist.primary_manager?.name ?? "No primary manager"}
              </p>
              <StatusBadge positive={artist.status === "active"}>
                {artist.status}
              </StatusBadge>
            </Link>
          ))}
        </div>
      )}
    </Workspace>
  );
}

export function ArtistCreatePage() {
  const router = useRouter();
  const { activeOrganizationId } = useAuth();
  const [message, setMessage] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeOrganizationId) return;
    const payload = Object.fromEntries(
      new FormData(event.currentTarget).entries(),
    );
    try {
      const artist = await apiRequest<Artist>("/api/artists/", {
        method: "POST",
        body: JSON.stringify({
          ...payload,
          organization_id: activeOrganizationId,
        }),
      });
      router.push(`/workspace/artists/${artist.id}`);
    } catch (caught) {
      setMessage(
        caught instanceof Error ? caught.message : "Unable to create artist.",
      );
    }
  }
  return (
    <Workspace>
      <PageHeader
        eyebrow="Artists"
        title="Create artist"
        description="Create the organization-owned business profile."
      />
      <div className="mt-5">
        <Notice message={message} error />
      </div>
      <form className="mt-7 max-w-3xl" onSubmit={submit}>
        <ArtistFields />
        <button className={`mt-7 ${buttonClass}`}>Create artist</button>
      </form>
    </Workspace>
  );
}

function ArtistDetailContent({
  data,
  platform,
  reload,
}: {
  data: Artist;
  platform?: boolean;
  reload: () => Promise<void>;
}) {
  const { activeOrganizationId, session } = useAuth();
  const router = useRouter();
  const organizationId = platform ? data.organization.id : activeOrganizationId;
  const [members, setMembers] = useState<Member[]>([]);
  const [overview, setOverview] = useState<ArtistOverview | null>(null);
  const [toolkit, setToolkit] = useState<ArtistToolkit | null>(null);
  const [selectedReleases, setSelectedReleases] = useState<string[]>([]);
  const [selectedDocuments, setSelectedDocuments] = useState<string[]>([]);
  const [message, setMessage] = useState("");
  const canManage =
    platform || hasOrganizationPermission(session, activeOrganizationId, "artist.manage");
  const canManageTeam =
    platform || hasOrganizationPermission(session, activeOrganizationId, "artist.team.manage");
  const pressImages = overview?.documents.filter((item) => item.content_type.startsWith("image/") || item.type === "artwork") ?? [];
  useEffect(() => {
    if (!organizationId || !canManageTeam) return;
    void apiRequest<Member[]>(
      "/api/organizations/" + organizationId + "/members/",
    ).then(setMembers);
  }, [organizationId, canManageTeam]);
  useEffect(() => {
    void apiRequest<ArtistOverview>(`/api/artists/${data.id}/overview/`).then(
      setOverview,
    );
    void apiRequest<ArtistToolkit>(`/api/artists/${data.id}/toolkit/`).then(setToolkit);
  }, [data.id]);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload = Object.fromEntries(
      new FormData(event.currentTarget).entries(),
    );
    try {
      await apiRequest(
        platform
          ? `/api/platform/artists/${data.id}/`
          : `/api/artists/${data.id}/`,
        { method: "PATCH", body: JSON.stringify(payload) },
      );
      setMessage("Artist updated.");
      await reload();
    } catch (caught) {
      setMessage(
        caught instanceof Error ? caught.message : "Unable to update artist.",
      );
    }
  }
  async function saveToolkit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
    const saved = await apiRequest<ArtistToolkit>(`/api/artists/${data.id}/toolkit/`, { method: "PATCH", body: JSON.stringify(payload) });
    setToolkit(saved);
    setMessage("Artist press kit updated.");
  }
  async function lifecycle(status: string) {
    if (!await confirmAction(`Change artist status to ${status}?`)) return;
    await apiRequest(
      platform
        ? `/api/platform/artists/${data.id}/`
        : `/api/artists/${data.id}/`,
      { method: "PATCH", body: JSON.stringify({ status }) },
    );
    await reload();
  }
  async function assign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const element = event.currentTarget; const form = new FormData(element);
    await apiRequest(`/api/artists/${data.id}/team/`, {
      method: "POST",
      body: JSON.stringify({
        membership_id: form.get("membership_id"),
        responsibility: form.get("responsibility"),
        is_primary: form.get("is_primary") === "on",
      }),
    });
    element.reset();
    await reload();
  }
  async function remove(assignment: Assignment) {
    if (!await confirmAction("Remove this team assignment?")) return;
    await apiRequest(`/api/artists/${data.id}/team/${assignment.id}/`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: false, is_primary: false }),
    });
    await reload();
  }
  async function link(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const element = event.currentTarget; const form = new FormData(element);
    const selected = members.find(
      (item) => item.id === form.get("membership_id"),
    );
    if (!selected) return;
    await apiRequest(`/api/artists/${data.id}/portal-links/`, {
      method: "POST",
      body: JSON.stringify({
        user_id: selected.user.id,
        relationship: form.get("relationship"),
      }),
    });
    await reload();
  }
  async function unlink(link: PortalLink) {
    if (!await confirmAction("Unlink this portal user?")) return;
    await apiRequest(
      "/api/artists/" + data.id + "/portal-links/" + link.id + "/unlink/",
      { method: "POST" },
    );
    await reload();
  }
  function prepareToolkitEmail() {
    if (!overview) return;
    const releases = overview.releases.filter((item) => selectedReleases.includes(item.id));
    const documents = overview.documents.filter((item) => selectedDocuments.includes(item.id));
    const lines = [
      `${data.stage_name} toolkit`,
      "",
      "Selected materials:",
      ...releases.map((item) => `Release: ${item.title} — https://evolve.nastycsa.com/workspace/music/releases/${item.id}`),
      ...documents.map((item) => `Document: ${item.title} — https://evolve.nastycsa.com/workspace/documents/${item.id}`),
      "",
      "Please sign in to Evolve to view authorized materials.",
    ];
    const params = new URLSearchParams({
      subject: `${data.stage_name} toolkit`,
      body: lines.join("\n"),
    });
    const recipient = data.booking_email || data.management_email || "";
    if (recipient) params.set("to", recipient);
    router.push(`/inbox?${params.toString()}`);
  }
  return (
    <>
      <Breadcrumbs
        items={
          platform
            ? [
                { label: "Platform", href: "/platform" },
                { label: "Artists", href: "/platform/artists" },
                { label: data.stage_name },
              ]
            : [
                { label: "Workspace", href: "/workspace" },
                { label: "Artists", href: "/workspace/artists" },
                { label: data.stage_name },
              ]
        }
      />
      <PageHeader
        eyebrow={platform ? "Platform artist" : "Artist"}
        title={data.stage_name}
        description={`${data.organization.name} / ${data.status}`}
        actions={
          canManage ? (
            <div className="flex gap-2">
              {data.status !== "active" && (
                <button
                  className={secondaryButtonClass}
                  onClick={() => void lifecycle("active")}
                >
                  Activate
                </button>
              )}
              {data.status === "active" && (
                <button
                  className={secondaryButtonClass}
                  onClick={() => void lifecycle("inactive")}
                >
                  Deactivate
                </button>
              )}
              {data.status !== "archived" && (
                <button
                  className={secondaryButtonClass}
                  onClick={() => void lifecycle("archived")}
                >
                  Archive
                </button>
              )}
            </div>
          ) : undefined
        }
      />
      <div className="mt-5">
        <Notice message={message} />
      </div>
      {overview && (
        <section className="mt-7 evolve-panel p-6">
          <div><p className="evolve-eyebrow text-xs font-semibold uppercase tracking-[0.14em]">Press kit</p><h2 className="mt-1 text-xl font-semibold">Artist information and rate card</h2><p className="mt-1 text-sm text-[var(--text-muted)]">Maintain approved copy for press, promoters, brands, and booking enquiries.</p></div>
          {canManage && toolkit && <form className="mt-5 grid gap-4" onSubmit={(event) => void saveToolkit(event)}><div className="grid gap-4 lg:grid-cols-2"><label className="grid gap-2 text-sm">Short bio<textarea className={`${fieldClass} min-h-28`} name="short_bio" defaultValue={toolkit.short_bio} placeholder="Approved short biography"/></label><label className="grid gap-2 text-sm">Statistics summary<textarea className={`${fieldClass} min-h-28`} name="stats_summary" defaultValue={toolkit.stats_summary} placeholder="Approved stats, milestones, and highlights"/></label><label className="grid gap-2 text-sm">Long bio<textarea className={`${fieldClass} min-h-40`} name="long_bio" defaultValue={toolkit.long_bio} placeholder="Approved press biography"/></label><label className="grid gap-2 text-sm">Rate card<textarea className={`${fieldClass} min-h-40`} name="rate_card" defaultValue={toolkit.rate_card} placeholder="Approved rates, inclusions, exclusions, and booking notes"/></label></div><button className={buttonClass}>Save press kit</button></form>}
          {!canManage && toolkit && <div className="mt-5 grid gap-4 lg:grid-cols-2"><div><h3 className="text-sm font-semibold">Short bio</h3><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[var(--text-secondary)]">{toolkit.short_bio || data.biography || "No approved short bio."}</p></div><div><h3 className="text-sm font-semibold">Rate card</h3><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[var(--text-secondary)]">{toolkit.rate_card || "No rate card published."}</p></div></div>}
        </section>
      )}
      {overview && (
        <section className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-md border border-neutral-800 p-4">
            <p className="text-sm text-neutral-500">Bookings</p>
            <p className="mt-2 text-2xl">{overview.bookings.length}</p>
            {overview.bookings.slice(0, 2).map((item) => (
              <Link
                className="mt-2 block text-sm"
                href={`/workspace/bookings/${item.id}`}
                key={item.id}
              >
                {item.reference} / {item.date}
              </Link>
            ))}
          </div>
          <div className="rounded-md border border-neutral-800 p-4">
            <p className="text-sm text-neutral-500">Music</p>
            <p className="mt-2 text-2xl">{overview.releases.length} releases</p>
            {overview.releases.slice(0, 2).map((item) => (
              <Link
                className="mt-2 block text-sm"
                href={`/workspace/music/releases/${item.id}`}
                key={item.id}
              >
                {item.title}
              </Link>
            ))}
          </div>
          <div className="rounded-md border border-neutral-800 p-4">
            <p className="text-sm text-neutral-500">Campaigns</p>
            <p className="mt-2 text-2xl">{overview.campaigns.length}</p>
            {overview.campaigns.slice(0, 2).map((item) => (
              <Link
                className="mt-2 block text-sm"
                href={`/workspace/campaigns/${item.id}`}
                key={item.id}
              >
                {item.name}
              </Link>
            ))}
          </div>
          <div className="rounded-md border border-neutral-800 p-4">
            <p className="text-sm text-neutral-500">Rights completeness</p>
            <p className="mt-2 text-sm">
              {overview.rights.works} Works /{" "}
              {overview.rights.tracks_with_master_rights} mastered Tracks
            </p>
            <p className="mt-2 text-sm text-neutral-500">
              {overview.rights.incomplete_master_splits} incomplete master /{" "}
              {overview.rights.incomplete_publishing_splits} publishing
            </p>
          </div>
        </section>
      )}
      <div className="mt-7 grid gap-7 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="grid gap-8">
          <section className="flex flex-col gap-5 sm:flex-row">
            <Avatar artist={data} large />
            <div>
              <StatusBadge positive={data.status === "active"}>
                {data.status}
              </StatusBadge>
              <p className="mt-4 text-sm text-neutral-400">
                {[data.city, data.country].filter(Boolean).join(", ") ||
                  "Location not set"}
              </p>
              <p className="mt-2 text-sm text-neutral-400">
                {data.email || "No artist email"}
              </p>
              <p className="mt-4 max-w-2xl leading-7 text-neutral-300">
                {data.biography || "No biography added."}
              </p>
            </div>
          </section>
          {canManage && (
            <form
              className="evolve-panel p-6"
              onSubmit={save}
            >
              <ArtistFields data={data} />
              <button className={`mt-7 ${buttonClass}`}>Save profile</button>
            </form>
          )}
          <section>
            <h2 className="font-semibold">Team</h2>
            {canManageTeam && (
              <form
                className="mt-4 grid gap-3 evolve-panel p-4 sm:grid-cols-[1fr_10rem_auto_auto]"
                onSubmit={assign}
              >
                <select className={fieldClass} name="membership_id" required>
                  <option value="">Select member</option>
                  {members
                    .filter((item) => item.is_active)
                    .map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.user.first_name || item.user.email}
                      </option>
                    ))}
                </select>
                <select className={fieldClass} name="responsibility">
                  {[
                    "manager",
                    "booking",
                    "marketing",
                    "finance",
                    "general",
                  ].map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
                <label className="flex items-center gap-2 text-sm">
                  <input name="is_primary" type="checkbox" />
                  Primary
                </label>
                <button className={buttonClass}>Assign</button>
              </form>
            )}
            <div className="mt-4 grid gap-3">
              {data.team
                ?.filter((item) => item.is_active)
                .map((item) => (
                  <div
                    className="grid gap-2 rounded-md border border-neutral-800 p-4 sm:grid-cols-[1fr_auto_auto]"
                    key={item.id}
                  >
                    <div>
                      <p>{item.member.name}</p>
                      <p className="text-xs text-neutral-500">
                        {item.member.email} / {item.member.organization_role}
                      </p>
                    </div>
                    <select
                      aria-label="Responsibility"
                      className={fieldClass}
                      disabled={!canManageTeam}
                      value={item.responsibility}
                      onChange={(event) =>
                        void apiRequest(
                          "/api/artists/" + data.id + "/team/" + item.id + "/",
                          {
                            method: "PATCH",
                            body: JSON.stringify({
                              responsibility: event.target.value,
                            }),
                          },
                        ).then(reload)
                      }
                    >
                      {[
                        "manager",
                        "booking",
                        "marketing",
                        "finance",
                        "general",
                      ].map((value) => (
                        <option key={value}>{value}</option>
                      ))}
                    </select>
                    {canManageTeam && (
                      <button
                        className={secondaryButtonClass}
                        onClick={() => void remove(item)}
                      >
                        Remove
                      </button>
                    )}
                  </div>
                ))}
            </div>
          </section>
          {canManageTeam && (
            <section>
              <h2 className="font-semibold">Portal users</h2>
              <form
                className="mt-4 grid gap-3 evolve-panel p-4 sm:grid-cols-[1fr_12rem_auto]"
                onSubmit={link}
              >
                <select className={fieldClass} name="membership_id" required>
                  <option value="">Select active member</option>
                  {members
                    .filter((item) => item.is_active)
                    .map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.user.email}
                      </option>
                    ))}
                </select>
                <select className={fieldClass} name="relationship">
                  {["artist", "assistant", "co_manager"].map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
                <button className={buttonClass}>Link user</button>
              </form>
              <div className="mt-3 text-sm text-neutral-400">
                {data.portal_links
                  ?.filter((item) => item.is_active)
                  .map((item) => (
                    <div
                      className="flex items-center justify-between gap-3 border-t border-neutral-800 py-3"
                      key={item.id}
                    >
                      <span>
                        {item.user.email} / {item.relationship}
                      </span>
                      <button
                        className={secondaryButtonClass}
                        onClick={() => void unlink(item)}
                      >
                        Unlink
                      </button>
                    </div>
                  ))}
              </div>
            </section>
          )}
          <section>
            <h2 className="font-semibold">Activity</h2>
            <div className="mt-3 grid gap-3">
              {data.activity?.map((item) => (
                <div
                  className="border-t border-neutral-800 pt-3 text-sm"
                  key={item.id}
                >
                  <p>{item.description}</p>
                  <p className="mt-1 text-xs text-neutral-500">
                    {item.actor ?? "System"} /{" "}
                    {new Date(item.created_at).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          </section>
        </div>
        <aside className="h-fit evolve-panel p-5">
          <h2 className="font-semibold">Contacts</h2>
          <dl className="mt-4 grid gap-3 text-sm">
            <dt className="text-neutral-500">Management</dt>
            <dd className="break-all">{data.management_email || "Not set"}</dd>
            <dt className="text-neutral-500">Booking</dt>
            <dd className="break-all">{data.booking_email || "Not set"}</dd>
            <dt className="text-neutral-500">Website</dt>
            <dd className="break-all">{data.website || "Not set"}</dd>
          </dl>
          <div className="mt-6 border-t border-neutral-800 pt-5">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-neutral-500">Artist toolkit</p>
            <div className="mt-3 grid gap-2 text-sm">
              <Link className="rounded border border-neutral-800 px-3 py-2 hover:border-amber-400" href={`/workspace/artists/${data.id}`}>Profile and team</Link>
              <Link className="rounded border border-neutral-800 px-3 py-2 hover:border-amber-400" href={`/workspace/calendar?artist=${data.id}`}>Upcoming schedule</Link>
              <Link className="rounded border border-neutral-800 px-3 py-2 hover:border-amber-400" href={`/workspace/music/releases?artist=${data.id}`}>Release catalogue</Link>
              <Link className="rounded border border-neutral-800 px-3 py-2 hover:border-amber-400" href={`/workspace/documents?artist=${data.id}`}>Approved toolkit files</Link>
            </div>
          </div>
        </aside>
      </div>
      {overview && (
        <section className="mt-7 evolve-panel p-6">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div><p className="evolve-eyebrow text-xs font-semibold uppercase tracking-[0.14em]">Artist toolkit</p><h2 className="mt-1 text-xl font-semibold">Approved catalogue and materials</h2><p className="mt-1 text-sm text-[var(--text-muted)]">Select current releases and approved files, then open a permissioned Mailroom draft for review before sending.</p></div>
            <Link className={secondaryButtonClass} href={`/workspace/documents?artist=${data.id}`}>Open all files</Link>
          </div>
          <div className="mt-5 grid gap-4 lg:grid-cols-[1.25fr_0.75fr]">
            <div>
              <h3 className="text-sm font-semibold">Latest releases</h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {overview.releases.slice(0, 6).map((release) => <div className="flex gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] p-3" key={release.id}>
                  <input aria-label={`Select ${release.title}`} checked={selectedReleases.includes(release.id)} className="mt-1" type="checkbox" onChange={(event) => setSelectedReleases((current) => event.target.checked ? [...current, release.id] : current.filter((id) => id !== release.id))}/>
                  {release.artwork_url ? <img className="size-16 rounded-lg object-cover" src={release.artwork_url} alt="" /> : <span className="grid size-16 place-items-center rounded-lg bg-[var(--background-soft)] text-xs font-semibold">{release.title.slice(0, 2).toUpperCase()}</span>}
                  <Link className="min-w-0" href={`/workspace/music/releases/${release.id}`}><strong className="block truncate">{release.title}</strong><span className="mt-1 block text-xs text-[var(--text-muted)]">{release.status} · {release.date || "Date not set"}</span>{release.upc_ean && <span className="mt-1 block text-xs text-[var(--text-muted)]">UPC {release.upc_ean}</span>}</Link>
                </div>)}
                {!overview.releases.length && <p className="text-sm text-[var(--text-muted)]">No releases linked to this artist.</p>}
              </div>
            </div>
            <div>
              <h3 className="text-sm font-semibold">Shared documents</h3>
              <div className="mt-3 grid gap-2">{overview.documents.slice(0, 6).map((document) => <div className="flex items-start gap-3 rounded-lg border border-[var(--border)] p-3 text-sm" key={document.id}><input aria-label={`Select ${document.title}`} checked={selectedDocuments.includes(document.id)} className="mt-1" type="checkbox" onChange={(event) => setSelectedDocuments((current) => event.target.checked ? [...current, document.id] : current.filter((id) => id !== document.id))}/><Link className="min-w-0 hover:text-[var(--accent-strong)]" href={`/workspace/documents/${document.id}`}><span className="font-medium">{document.title}</span><span className="mt-1 block text-xs text-[var(--text-muted)]">{document.type}</span></Link></div>)}{!overview.documents.length && <p className="text-sm text-[var(--text-muted)]">No approved toolkit files linked.</p>}</div>
            </div>
          </div>
          <div className="mt-6 border-t border-[var(--border)] pt-5">
            <div className="flex flex-wrap items-end justify-between gap-3"><div><h3 className="text-sm font-semibold">Press images</h3><p className="mt-1 text-sm text-[var(--text-muted)]">Artist-linked image assets for press, promoters, campaigns, and approved outreach.</p></div><Link className={secondaryButtonClass} href={`/workspace/documents?artist=${data.id}&type=artwork`}>Manage image assets</Link></div>
            {pressImages.length ? <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{pressImages.slice(0, 8).map((image) => <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-raised)]" key={image.id}>{image.external_url ? <img className="aspect-[4/3] w-full object-cover" src={image.external_url} alt={image.title} /> : <div className="grid aspect-[4/3] place-items-center bg-[var(--background-soft)] px-4 text-center text-xs text-[var(--text-muted)]">Private image<br />Open to view securely</div>}<div className="flex items-start gap-2 p-3"><input aria-label={`Select ${image.title}`} checked={selectedDocuments.includes(image.id)} className="mt-1" type="checkbox" onChange={(event) => setSelectedDocuments((current) => event.target.checked ? [...current, image.id] : current.filter((id) => id !== image.id))}/><Link className="min-w-0 text-sm hover:text-[var(--accent-strong)]" href={`/workspace/documents/${image.id}`}><span className="block truncate font-medium">{image.title}</span><span className="mt-1 block truncate text-xs text-[var(--text-muted)]">{image.original_filename || image.content_type || "Image asset"}</span></Link></div></div>)}</div> : <p className="mt-3 rounded-lg border border-dashed border-[var(--border)] p-5 text-sm text-[var(--text-muted)]">No press images linked yet. Upload an artwork/image document below and link it to this artist.</p>}
          </div>
          <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border)] pt-4"><p className="text-sm text-[var(--text-muted)]">{selectedReleases.length + selectedDocuments.length} toolkit item(s) selected.</p><button className={buttonClass} disabled={!selectedReleases.length && !selectedDocuments.length} onClick={prepareToolkitEmail} type="button">Prepare email in Mailroom</button></div>
        </section>
      )}
      {!platform && (
        <div className="mt-7">
          <EntityDocumentsSection allowUpload={canManage} entityType="artist" entityId={data.id} />
        </div>
      )}
    </>
  );
}

export function ArtistDetailPage({ id }: { id: string }) {
  const [data, setData] = useState<Artist | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      setData(await apiRequest<Artist>(`/api/artists/${id}/`));
      setError("");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to load artist.",
      );
    }
  }, [id]);
  useEffect(() => {
    let cancelled = false;
    apiRequest<Artist>("/api/artists/" + id + "/")
      .then((next) => {
        if (!cancelled) setData(next);
      })
      .catch((caught) => {
        if (!cancelled)
          setError(
            caught instanceof Error ? caught.message : "Unable to load artist.",
          );
      });
    return () => {
      cancelled = true;
    };
  }, [id]);
  return (
    <Workspace>
      {error ? (
        <Notice message={error} error />
      ) : data ? (
        <ArtistDetailContent data={data} reload={load} />
      ) : (
        <p className="py-12 text-neutral-500">Loading artist...</p>
      )}
    </Workspace>
  );
}

export function PlatformArtistsPage() {
  const [data, setData] = useState<Artist[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  useEffect(() => {
    void apiRequest<Artist[]>("/api/platform/artists/").then(setData);
  }, []);
  const filtered = data.filter(
    (item) =>
      (!query ||
        `${item.stage_name} ${item.organization.name}`
          .toLowerCase()
          .includes(query.toLowerCase())) &&
      (!status || item.status === status),
  );
  return (
    <Platform>
      <PageHeader
        eyebrow="Platform"
        title="Artists"
        description="Cross-organization artist inventory."
      />
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <input
          className={fieldClass}
          placeholder="Search artist or organization"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          className={fieldClass}
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">All statuses</option>
          {["active", "inactive", "archived"].map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
      </div>
      <div className="mt-7 grid gap-3">
        {filtered.map((artist) => (
          <Link
            className="grid gap-3 evolve-panel p-5 sm:grid-cols-[1fr_auto_auto_auto]"
            href={`/platform/artists/${artist.id}`}
            key={artist.id}
          >
            <div>
              <p>{artist.stage_name}</p>
              <p className="text-sm text-neutral-500">
                {artist.organization.name}
              </p>
            </div>
            <span>{artist.team_count} team</span>
            <span>{artist.portal_user_count} portal</span>
            <StatusBadge positive={artist.status === "active"}>
              {artist.status}
            </StatusBadge>
          </Link>
        ))}
      </div>
    </Platform>
  );
}
export function PlatformArtistDetailPage({ id }: { id: string }) {
  const [data, setData] = useState<Artist | null>(null);
  const load = useCallback(
    async () =>
      setData(await apiRequest<Artist>(`/api/platform/artists/${id}/`)),
    [id],
  );
  useEffect(() => {
    let cancelled = false;
    apiRequest<Artist>("/api/platform/artists/" + id + "/").then((next) => {
      if (!cancelled) setData(next);
    });
    return () => {
      cancelled = true;
    };
  }, [id]);
  return (
    <Platform>
      {data ? (
        <ArtistDetailContent data={data} platform reload={load} />
      ) : (
        <p className="py-12 text-neutral-500">Loading artist...</p>
      )}
    </Platform>
  );
}

export function ArtistPortalPage() {
  const [data, setData] = useState<PortalArtist[] | null>(null);
  const [selected, setSelected] = useState("");
  useEffect(() => {
    void apiRequest<PortalArtist[]>("/api/artist-portal/").then((artists) => {
      setData(artists);
      setSelected(artists[0]?.id ?? "");
    });
  }, []);
  const artist = data?.find((item) => item.id === selected);
  return (
    <RouteGuard portal="artist">
      <AppShell organizationScoped>
        {data === null ? (
          <p className="py-12 text-neutral-500">Loading artist portal...</p>
        ) : data.length === 0 ? (
          <EmptyState
            title="Artist portal unavailable"
            detail="Your account is not linked to an active artist profile."
          />
        ) : (
          <>
            <PageHeader
              eyebrow="Artist portal"
              title={artist?.stage_name ?? "Artist"}
              description={artist?.organization}
            />
            {data.length > 1 && (
              <select
                className={`mt-6 max-w-sm ${fieldClass}`}
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
              >
                {data.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.stage_name}
                  </option>
                ))}
              </select>
            )}
            {artist && (
              <div className="mt-7 grid gap-7 lg:grid-cols-[1fr_20rem]">
                <section>
                  <div className="flex flex-col gap-5 sm:flex-row">
                    {artist.profile_image_url ? (
                      <Image
                        unoptimized
                        alt=""
                        className="size-28 rounded-md object-cover"
                        height={112}
                        src={artist.profile_image_url}
                        width={112}
                      />
                    ) : (
                      <span className="grid size-28 place-items-center rounded-md bg-neutral-800 text-3xl">
                        {artist.stage_name.slice(0, 2).toUpperCase()}
                      </span>
                    )}
                    <div>
                      <StatusBadge positive={artist.status === "active"}>
                        {artist.status}
                      </StatusBadge>
                      <p className="mt-4 text-neutral-400">
                        {[artist.city, artist.country]
                          .filter(Boolean)
                          .join(", ")}
                      </p>
                      <p className="mt-4 max-w-2xl leading-7 text-neutral-300">
                        {artist.biography || "No biography available."}
                      </p>
                    </div>
                  </div>
                </section>
                <aside className="evolve-panel p-5">
                  <h2 className="font-semibold">Your team</h2>
                  {artist.team.map((item) => (
                    <div
                      className="mt-4 border-t border-neutral-800 pt-3 text-sm"
                      key={`${item.email}-${item.responsibility}`}
                    >
                      <p>{item.name}</p>
                      <p className="text-neutral-500">
                        {item.responsibility}
                        {item.is_primary ? " / primary" : ""}
                      </p>
                      <p className="break-all text-neutral-500">{item.email}</p>
                    </div>
                  ))}
                </aside>
              </div>
            )}
            {artist && <ArtistMusicSection artistId={artist.id} />}
            {artist && <ArtistCampaignSection artistId={artist.id} />}
            {artist && <ArtistContractsSection artistId={artist.id} />}
            {artist && <ArtistScheduleSection artistId={artist.id} />}
            {artist && <ArtistDocumentsSection artistId={artist.id} />}
          </>
        )}
      </AppShell>
    </RouteGuard>
  );
}
