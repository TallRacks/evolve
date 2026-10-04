"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth/auth-provider";
import { hasOrganizationPermission } from "@/lib/auth/access";
import { RouteGuard } from "@/components/auth/route-guard";
import {
  buttonClass,
  EmptyState,
  fieldClass,
  PageHeader,
  secondaryButtonClass,
  StatCard,
  StatusBadge,
} from "@/components/ui/page";
import { apiRequest } from "@/lib/api/client";
import { confirmAction, promptAction } from "@/components/ui/action-dialog";
type Party = {
  id: string;
  display_name: string;
  party_type: string;
  is_active: boolean;
};
type Track = { id: string; title: string };
type Work = {
  id: string;
  title: string;
  status: string;
  iswc: string;
  publishing_total: string;
  track_links: { id: string; track_title: string; relationship_type: string }[];
  contributors: { id: string; party_name: string; role: string; share_percentage: string }[];
  publishing_rights: {
    id: string;
    party_name: string;
    right_type: string;
    ownership_percentage: string;
    territory_code: string;
  }[];
};
type Allocation = {
  id: string;
  party_name: string;
  percentage: string;
  amount: string;
};
type Line = {
  id: string;
  platform: string;
  rights_basis: string;
  net_amount: string;
  allocated_amount: string;
  allocations: Allocation[];
};
type Statement = {
  id: string;
  statement_reference: string;
  source_name: string;
  status: string;
  period_start: string;
  period_end: string;
  currency: string;
  declared_total: string | null;
  calculated_total: string;
  variance: string | null;
  lines: Line[];
};
const W = ({ children }: { children: React.ReactNode }) => (
  <RouteGuard portal="workspace">
    <AppShell organizationScoped>{children}</AppShell>
  </RouteGuard>
);
const P = ({ children }: { children: React.ReactNode }) => (
  <RouteGuard portal="platform">
    <AppShell>{children}</AppShell>
  </RouteGuard>
);
const cash = (v: string, c: string) =>
  new Intl.NumberFormat(undefined, { style: "currency", currency: c }).format(
    Number(v),
  );
export function RightsOverviewPage({
  platform = false,
}: {
  platform?: boolean;
}) {
  const { activeOrganizationId: o, session } = useAuth();
  const canManage = hasOrganizationPermission(session, o, "rights.manage");
  const [d, setD] = useState<{
    works: number;
    parties: number;
    incomplete_master: number;
    incomplete_publishing: number;
  } | null>(null);
  useEffect(() => {
    if (o && !platform)
      void apiRequest<typeof d>(
        "/api/rights/overview/?organization_id=" + o,
      ).then(setD);
  }, [o, platform]);
  const b = (
    <>
      <PageHeader
        eyebrow={platform ? "Platform" : "Rights & royalties"}
        title="Rights overview"
        description="A control surface for credits, ownership splits, and statement attribution. Rights data is separate from earnings and payment records."
        actions={
          !platform && canManage ? (
            <Link className={buttonClass} href="/workspace/rights/works/new">
              Create Work
            </Link>
          ) : undefined
        }
      />
      {d && (
        <div className="mt-7 grid gap-4 sm:grid-cols-4">
          <StatCard label="Works" value={d.works} />
          <StatCard label="Parties" value={d.parties} />
          <StatCard label="Incomplete masters" value={d.incomplete_master} />
          <StatCard
            label="Incomplete publishing"
            value={d.incomplete_publishing}
          />
        </div>
      )}
      <div className="mt-7 flex gap-3">
        <Link
          className={secondaryButtonClass}
          href={(platform ? "/platform" : "/workspace") + "/rights/works"}
        >
          Works
        </Link>
        <Link
          className={secondaryButtonClass}
          href={(platform ? "/platform" : "/workspace") + "/rights/parties"}
        >
          Parties
        </Link>
        <Link
          className={secondaryButtonClass}
          href={(platform ? "/platform" : "/workspace") + "/royalties"}
        >
          Royalties
        </Link>
      </div>
    </>
  );
  return platform ? <P>{b}</P> : <W>{b}</W>;
}
export function WorkListPage({ platform = false }: { platform?: boolean }) {
  const { activeOrganizationId: o, session } = useAuth();
  const canManage = hasOrganizationPermission(session, o, "rights.manage");
  const [x, setX] = useState<Work[]>([]);
  useEffect(() => {
    const u = platform
      ? "/api/platform/rights/works/"
      : "/api/rights/works/?organization_id=" + o;
    if (platform || o) void apiRequest<Work[]>(u).then(setX);
  }, [o, platform]);
  const b = (
    <>
      <PageHeader
        eyebrow="Rights"
        title="Works"
        actions={
          !platform && canManage ? (
            <Link className={buttonClass} href="/workspace/rights/works/new">
              New Work
            </Link>
          ) : undefined
        }
      />
      <div className="mt-7 grid gap-3">
        {x.map((i) => (
          <Link
            className="grid grid-cols-[1fr_auto_auto] gap-3 rounded-md border border-neutral-800 p-5"
            href={
              (platform ? "/platform" : "/workspace") + "/rights/works/" + i.id
            }
            key={i.id}
          >
            <div>
              <strong>{i.title}</strong>
              <p className="text-sm text-neutral-500">
                {i.iswc || "No ISWC"} / {i.track_links.length} recordings
              </p>
            </div>
            <StatusBadge positive={i.status === "active"}>
              {i.status}
            </StatusBadge>
            <span>{i.publishing_total}% publishing</span>
          </Link>
        ))}
        {!x.length && (
          <EmptyState
            title="No Works"
            detail="No compositions match this view."
          />
        )}
      </div>
    </>
  );
  return platform ? <P>{b}</P> : <W>{b}</W>;
}
export function NewWorkPage() {
  const organization = useAuth().activeOrganizationId;
  const r = useRouter();
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const element = e.currentTarget;
    const data = {
      ...Object.fromEntries(new FormData(element)),
      organization,
    };
    const x = await apiRequest<Work>("/api/rights/works/", {
      method: "POST",
      body: JSON.stringify(data),
    });
    r.push("/workspace/rights/works/" + x.id);
  }
  return (
    <W>
      <PageHeader
        eyebrow="Rights"
        title="Create Work"
        description="A composition is separate from Track recordings and descriptive Music credits."
      />
      <form
        className="mt-7 grid max-w-2xl gap-4 sm:grid-cols-2"
        onSubmit={save}
      >
        <input
          className={fieldClass}
          name="title"
          placeholder="Title"
          required
        />
        <input
          className={fieldClass}
          name="alternate_title"
          placeholder="Alternate title"
        />
        <input className={fieldClass} name="iswc" placeholder="ISWC" />
        <input
          className={fieldClass}
          name="internal_reference"
          placeholder="Internal reference"
        />
        <input className={fieldClass} name="language" placeholder="Language" />
        <textarea
          className="min-h-24 rounded-md border border-neutral-700 bg-neutral-950 p-3"
          name="notes"
        />
        <button className={buttonClass}>Create Work</button>
      </form>
    </W>
  );
}
export function WorkDetailPage({ platform = false }: { platform?: boolean }) {
  const { id } = useParams<{ id: string }>();
  const o = useAuth().activeOrganizationId;
  const [d, setD] = useState<Work | null>(null);
  const [parties, setParties] = useState<Party[]>([]);
  const [tracks, setTracks] = useState<Track[]>([]);
  const load = useCallback(
    () => apiRequest<Work>("/api/rights/works/" + id + "/").then(setD),
    [id],
  );
  useEffect(() => {
    void load();
    if (!platform)
      void Promise.all([
        apiRequest<Party[]>("/api/rights/parties/"),
        apiRequest<Track[]>("/api/music/tracks/?organization_id=" + o),
      ]).then((x) => {
        setParties(x[0]);
        setTracks(x[1]);
      });
  }, [load, platform, o]);
  async function add(path: string, e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const element = e.currentTarget;
    await apiRequest(path, {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(new FormData(element))),
    });
    element.reset();
    await load();
  }
  const total = Number(d?.publishing_total || 0);
  const b = (
    <>
      {d && (
        <PageHeader
          eyebrow="Work"
          title={d.title}
          description={d.iswc || "No official ISWC recorded"}
        />
      )}{" "}
      {d && (
        <>
          <div className="mt-7 grid gap-4 sm:grid-cols-3">
            <StatCard label="Recordings" value={d.track_links.length} />
            <StatCard label="Publishing allocated" value={total + "%"} />
            <StatCard
              label="Unallocated"
              value={Math.max(0, 100 - total) + "%"}
            />
          </div>
          <h2 className="mt-8 font-semibold">Recordings</h2>
          {d.track_links.map((x) => (
            <p className="mt-3" key={x.id}>
              {x.track_title} / {x.relationship_type}
            </p>
          ))}
          {!platform && (
            <form
              className="mt-4 grid gap-3 sm:grid-cols-3"
              onSubmit={(e) =>
                void add("/api/rights/works/" + id + "/tracks/", e)
              }
            >
              <select className={fieldClass} name="track" required>
                <option value="">Select recording</option>
                {tracks.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.title}
                  </option>
                ))}
              </select>
              <select className={fieldClass} name="relationship_type">
                {["primary", "medley", "adaptation", "other"].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
              <button className={secondaryButtonClass}>Link recording</button>
            </form>
          )}
          <h2 className="mt-8 font-semibold">Split sheet contributors</h2><p className="mt-1 text-sm text-neutral-500">Contributor shares must total no more than 100%.</p>
          {d.contributors.map((x) => (
            <p className="mt-3 grid grid-cols-3 border-t border-neutral-800 pt-3 text-sm" key={x.id}>
              <span>{x.party_name}</span><span>{x.role}</span><span>{x.share_percentage}%</span>
            </p>
          ))}
          {!platform && (
            <form
              className="mt-4 grid gap-3 sm:grid-cols-4"
              onSubmit={(e) =>
                void add("/api/rights/works/" + id + "/contributors/", e)
              }
            >
              <select className={fieldClass} name="party" required>
                {parties.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.display_name}
                  </option>
                ))}
              </select>
              <select className={fieldClass} name="role">
                {["songwriter", "composer", "lyricist", "arranger", "other"].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
              <input className={fieldClass} name="share_percentage" type="number" min="0" max="100" step="0.0001" placeholder="Share %" required />
              <button className={secondaryButtonClass}>Add contributor</button>
            </form>
          )}
          <h2 className="mt-8 font-semibold">Publishing rights</h2>
          {d.publishing_rights.map((x) => (
            <p className="mt-3 grid grid-cols-4" key={x.id}>
              <span>{x.party_name}</span>
              <span>{x.right_type}</span>
              <span>{x.ownership_percentage}%</span>
              <span>{x.territory_code}</span>
            </p>
          ))}
          {!platform && (
            <form
              className="mt-5 grid gap-3 sm:grid-cols-5"
              onSubmit={(e) =>
                void add("/api/rights/works/" + id + "/publishing/", e)
              }
            >
              <select className={fieldClass} name="party">
                {parties.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.display_name}
                  </option>
                ))}
              </select>
              <select className={fieldClass} name="right_type">
                {["writer", "publisher", "administrator", "other"].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
              <input
                className={fieldClass}
                name="ownership_percentage"
                type="number"
                step="0.0001"
                placeholder="Percent"
              />
              <input
                className={fieldClass}
                name="territory_code"
                defaultValue="WORLDWIDE"
              />
              <button className={buttonClass}>Add</button>
            </form>
          )}
        </>
      )}
    </>
  );
  return platform ? <P>{b}</P> : <W>{b}</W>;
}
export function PartiesPage({ platform = false }: { platform?: boolean }) {
  const organization = useAuth().activeOrganizationId;
  const [x, setX] = useState<Party[]>([]);
  const load = useCallback(
    () =>
      apiRequest<Party[]>(
        organization && !platform
          ? "/api/rights/parties/?organization_id=" + organization
          : "/api/rights/parties/",
      ).then(setX),
    [organization, platform],
  );
  useEffect(() => {
    if (platform || organization) void load();
  }, [load, organization, platform]);
  async function save(e: FormEvent<HTMLFormElement>) {
    const element = e.currentTarget;
    e.preventDefault();
    await apiRequest("/api/rights/parties/", {
      method: "POST",
      body: JSON.stringify({
        ...Object.fromEntries(new FormData(element)),
        organization,
      }),
    });
    element.reset();
    await load();
  }
  const b = (
    <>
      <PageHeader
        eyebrow="Rights"
        title="Rights parties"
        description="Parties do not require Evolve accounts."
      />
      {!platform && (
        <form className="mt-6 flex gap-3" onSubmit={save}>
          <input
            className={fieldClass}
            name="display_name"
            placeholder="Display name"
          />
          <select className={fieldClass} name="party_type">
            {[
              "artist",
              "songwriter",
              "producer",
              "publisher",
              "label",
              "company",
              "estate",
              "other",
            ].map((i) => (
              <option key={i}>{i}</option>
            ))}
          </select>
          <button className={buttonClass}>Add</button>
        </form>
      )}
      <div className="mt-7">
        {x.map((i) => (
          <p
            className="mt-3 grid grid-cols-3 rounded-md border border-neutral-800 p-4"
            key={i.id}
          >
            <strong>{i.display_name}</strong>
            <span>{i.party_type}</span>
            <span>{i.is_active ? "active" : "inactive"}</span>
          </p>
        ))}
      </div>
    </>
  );
  return platform ? <P>{b}</P> : <W>{b}</W>;
}
export function RoyaltiesOverviewPage({
  platform = false,
}: {
  platform?: boolean;
}) {
  const { activeOrganizationId: o, session } = useAuth();
  const canManage = hasOrganizationPermission(session, o, "royalties.manage");
  const [x, setX] = useState<Statement[]>([]);
  useEffect(() => {
    const u = platform
      ? "/api/platform/royalties/statements/"
      : "/api/royalties/statements/?organization_id=" + o;
    if (platform || o) void apiRequest<Statement[]>(u).then(setX);
  }, [o, platform]);
  const unallocated = x.reduce<Record<string, number>>((totals, statement) => {
    if (statement.status !== "draft") return totals;
    const amount = statement.lines.reduce(
      (total, line) =>
        total + Number(line.net_amount) - Number(line.allocated_amount),
      0,
    );
    totals[statement.currency] = (totals[statement.currency] ?? 0) + amount;
    return totals;
  }, {});
  const b = (
    <>
      <PageHeader
        eyebrow="Rights & royalties"
        title="Royalty overview"
        actions={
          !platform && canManage ? (
            <Link
              className={buttonClass}
              href="/workspace/royalties/statements/new"
            >
              New statement
            </Link>
          ) : undefined
        }
      />
      <div className="mt-7 grid gap-4 sm:grid-cols-2">
        <StatCard
          label="Draft statements"
          value={x.filter((i) => i.status === "draft").length}
        />
        <StatCard
          label="Finalized statements"
          value={x.filter((i) => i.status === "finalized").length}
        />
      </div>
      {Object.entries(unallocated).length > 0 && (
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          {Object.entries(unallocated).map(([currency, amount]) => (
            <StatCard
              key={currency}
              label={`Unallocated (${currency})`}
              value={cash(amount.toFixed(2), currency)}
            />
          ))}
        </div>
      )}
      <Link
        className={"mt-7 " + secondaryButtonClass}
        href={(platform ? "/platform" : "/workspace") + "/royalties/statements"}
      >
        View statements
      </Link>
    </>
  );
  return platform ? <P>{b}</P> : <W>{b}</W>;
}
export function StatementListPage({
  platform = false,
}: {
  platform?: boolean;
}) {
  const { activeOrganizationId: o, session } = useAuth();
  const canManage = hasOrganizationPermission(session, o, "royalties.manage");
  const [x, setX] = useState<Statement[]>([]);
  useEffect(() => {
    const u = platform
      ? "/api/platform/royalties/statements/"
      : "/api/royalties/statements/?organization_id=" + o;
    if (platform || o) void apiRequest<Statement[]>(u).then(setX);
  }, [o, platform]);
  const b = (
    <>
      <PageHeader eyebrow="Royalties" title="Statements" actions={!platform && canManage ? <Link className={buttonClass} href="/workspace/royalties/statements/new">New statement</Link> : undefined} />
      <div className="mt-7">
        {x.map((i) => (
          <Link
            className="mt-3 grid grid-cols-[1fr_auto_auto] gap-3 rounded-md border border-neutral-800 p-5"
            href={
              (platform ? "/platform" : "/workspace") +
              "/royalties/statements/" +
              i.id
            }
            key={i.id}
          >
            <span>
              {i.statement_reference} / {i.source_name}
            </span>
            <StatusBadge positive={i.status === "finalized"}>
              {i.status}
            </StatusBadge>
            <span>{cash(i.calculated_total, i.currency)}</span>
          </Link>
        ))}
      </div>
    </>
  );
  return platform ? <P>{b}</P> : <W>{b}</W>;
}
export function NewStatementPage() {
  const organization = useAuth().activeOrganizationId;
  const r = useRouter();
  const [sources, setSources] = useState<{ id: string; name: string; source_type: string }[]>([]);
  const [documents, setDocuments] = useState<{ id: string; title: string; document_type: string }[]>([]);
  const [sourceId, setSourceId] = useState("");
  useEffect(() => {
    if (!organization) return;
    void Promise.all([
      apiRequest<{ id: string; name: string; source_type: string }[]>(`/api/royalties/sources/?organization_id=${organization}`),
      apiRequest<{ id: string; title: string; document_type: string }[]>(`/api/documents/?organization=${organization}`),
    ]).then(([sourceRows, documentRows]) => {
      setSources(sourceRows);
      setDocuments(documentRows);
    });
  }, [organization]);
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const element = e.currentTarget;
    const d: { [key: string]: FormDataEntryValue | string | null } = {
      ...Object.fromEntries(new FormData(element)),
      organization,
    };
    const sourceFile = d.source_file instanceof File && d.source_file.size > 0 ? d.source_file : null;
    delete d.source_file;
    if (sourceFile && organization) {
      const upload = new FormData();
      upload.set("organization", organization);
      upload.set("title", `${String(d.source_name || "Royalty statement")} · ${String(d.period_end || "source document")}`);
      upload.set("document_type", "other");
      upload.set("visibility", "restricted");
      upload.set("file", sourceFile);
      const document = await apiRequest<{ id: string }>("/api/documents/upload/", { method: "POST", body: upload });
      d.source_document = document.id;
    }
    const selectedSource = sources.find((item) => item.id === sourceId);
    if (selectedSource) {
      d.source = selectedSource.id;
      d.source_name = selectedSource.name;
      d.source_type = selectedSource.source_type;
    }
    if (!d.declared_total) d.declared_total = null;
    const x = await apiRequest<Statement>("/api/royalties/statements/", {
      method: "POST",
      body: JSON.stringify(d),
    });
    r.push("/workspace/royalties/statements/" + x.id);
  }
  return (
    <W>
      <PageHeader
        eyebrow="Royalties"
        title="Create statement"
        description="Earnings attribution is not a payout or Finance payment."
      />
      <form
        className="mt-7 grid max-w-2xl gap-4 sm:grid-cols-2"
        onSubmit={save}
      >
        <select className={fieldClass} name="source" value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
          <option value="">Select configured source</option>
          {sources.map((source) => <option key={source.id} value={source.id}>{source.name} · {source.source_type}</option>)}
        </select>
        <input className={fieldClass} name="source_name" placeholder="Source name (or add one in Royalty Hub)" />
        <select className={fieldClass} name="source_type" defaultValue="distributor">
          <option value="distributor">Distributor</option>
          <option value="label">Label</option>
          <option value="publisher">Publisher</option>
          <option value="society">Collection society</option>
        </select>
        <input className={fieldClass} name="currency" defaultValue="ZAR" />
        <input className={fieldClass} name="period_start" type="date" />
        <input className={fieldClass} name="period_end" type="date" />
        <input
          className={fieldClass}
          name="declared_total"
          type="number"
          step="0.01"
          placeholder="Declared total"
        />
        <select className={fieldClass} name="source_document">
          <option value="">Attach source statement (optional)</option>
          {documents.map((document) => <option key={document.id} value={document.id}>{document.title} · {document.document_type}</option>)}
        </select>
        <label className="text-sm text-[var(--text-secondary)] sm:col-span-2">Or upload the source statement privately
          <input className={`mt-2 ${fieldClass}`} name="source_file" type="file" accept=".pdf,.csv,.xlsx" />
          <span className="mt-1 block text-xs text-[var(--text-muted)]">The file is stored in private document storage and linked to this statement.</span>
        </label>
        <textarea className="min-h-24 rounded-md border border-[var(--border)] bg-[var(--surface)] p-3 sm:col-span-2" name="internal_notes" placeholder="Internal notes" />
        <button className={buttonClass}>Create draft</button>
      </form>
    </W>
  );
}
export function StatementDetailPage({
  platform = false,
}: {
  platform?: boolean;
}) {
  const { id } = useParams<{ id: string }>();
  const o = useAuth().activeOrganizationId;
  const [d, setD] = useState<Statement | null>(null);
  const [parties, setParties] = useState<Party[]>([]);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [importMessage, setImportMessage] = useState("");
  const load = useCallback(
    () =>
      apiRequest<Statement>("/api/royalties/statements/" + id + "/").then(setD),
    [id],
  );
  useEffect(() => {
    void load();
    if (!platform && o)
      void Promise.all([
        apiRequest<Party[]>("/api/rights/parties/?organization_id=" + o),
        apiRequest<Track[]>("/api/music/tracks/?organization_id=" + o),
      ]).then((x) => {
        setParties(x[0]);
        setTracks(x[1]);
      });
  }, [load, platform, o]);
  async function act(name: string) {
    if (name === "finalize" && !await confirmAction("Finalize and freeze this statement?"))
      return;
    await apiRequest("/api/royalties/statements/" + id + "/" + name + "/", {
      method: "POST",
      body: JSON.stringify(
        name === "void" ? { reason: await promptAction("Void reason") } : {},
      ),
    });
    await load();
  }
  async function importCsv(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const result = await apiRequest<{ imported: number; skipped: number; errors: string[] }>(`/api/royalties/statements/${id}/import/`, { method: "POST", body: form });
      setImportMessage(`Imported ${result.imported} lines; skipped ${result.skipped} duplicates.${result.errors.length ? ` ${result.errors.length} rows need review.` : ""}`);
      event.currentTarget.reset();
      await load();
    } catch (error) {
      setImportMessage(error instanceof Error ? error.message : "Unable to import royalty statement.");
    }
  }
  const b = (
    <>
      {d && (
        <PageHeader
          eyebrow="Royalty statement"
          title={d.statement_reference}
          description={
            d.source_name + " / " + d.period_start + " to " + d.period_end
          }
          actions={
            !platform ? (
              <div>
                {d.status === "draft" && (
                  <button
                    className={buttonClass}
                    onClick={() => void act("finalize")}
                  >
                    Finalize
                  </button>
                )}
                {d.status === "finalized" && (
                  <button
                    className={secondaryButtonClass}
                    onClick={() => void act("void")}
                  >
                    Void
                  </button>
                )}
              </div>
            ) : undefined
          }
        />
      )}{" "}
      {d && (
        <>
          <div className="mt-7 grid gap-4 sm:grid-cols-4">
            <StatCard label="Status" value={d.status} />
            <StatCard
              label="Declared"
              value={
                d.declared_total
                  ? cash(d.declared_total, d.currency)
                  : "Not supplied"
              }
            />
            <StatCard
              label="Calculated"
              value={cash(d.calculated_total, d.currency)}
            />
            <StatCard
              label="Variance"
              value={d.variance ? cash(d.variance, d.currency) : "N/A"}
            />
          </div>
          <h2 className="mt-8 font-semibold">Lines and allocations</h2>
          {!platform && d.status === "draft" && (
            <form className="mt-4 flex flex-wrap items-end gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-4" onSubmit={(event) => void importCsv(event)}>
              <label className="text-sm text-[var(--text-secondary)]">Import CSV or XLSX statement
                <input className={`mt-2 ${fieldClass}`} name="file" type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" required />
              </label>
              <button className={secondaryButtonClass}>Import lines</button>
              <span className="text-xs text-[var(--text-muted)]">Use headers such as ISRC, UPC, Track, Gross, Deductions, Platform, and Rights Basis.</span>
            </form>
          )}
          {importMessage && <p className="mt-3 text-sm text-[var(--accent-strong)]" role="status">{importMessage}</p>}
          {!platform && d.status === "draft" && (
            <form
              className="mt-4 grid gap-3 sm:grid-cols-4"
              onSubmit={async (e) => {
                e.preventDefault();
                const element = e.currentTarget;
                await apiRequest(
                  "/api/royalties/statements/" + id + "/lines/",
                  {
                    method: "POST",
                    body: JSON.stringify(
                      Object.fromEntries(new FormData(element)),
                    ),
                  },
                );
                element.reset();
                await load();
              }}
            >
              <select className={fieldClass} name="track">
                <option value="">Resolved Track (optional)</option>
                {tracks.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.title}
                  </option>
                ))}
              </select>
              <input
                className={fieldClass}
                name="external_track_reference"
                placeholder="Track reference"
              />
              <input
                className={fieldClass}
                name="platform"
                placeholder="Platform / source"
              />
              <select className={fieldClass} name="rights_basis">
                {["master", "publishing", "mixed", "other"].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
              <input
                className={fieldClass}
                name="territory_code"
                defaultValue="WORLDWIDE"
              />
              <input
                className={fieldClass}
                name="usage_type"
                placeholder="Usage"
              />
              <input
                className={fieldClass}
                name="quantity"
                type="number"
                step="0.0001"
                placeholder="Quantity"
              />
              <input
                className={fieldClass}
                name="gross_amount"
                type="number"
                step="0.01"
                placeholder="Gross"
                required
              />
              <input
                className={fieldClass}
                name="deductions"
                type="number"
                step="0.01"
                defaultValue="0"
              />
              <button className={buttonClass}>Add line</button>
            </form>
          )}
          {d.lines.map((line) => (
            <div
              className="mt-4 rounded-md border border-neutral-800 p-5"
              key={line.id}
            >
              <p>
                {line.platform || "Statement line"} / {line.rights_basis} /{" "}
                {cash(line.net_amount, d.currency)} net /{" "}
                {cash(line.allocated_amount, d.currency)} allocated
              </p>
              {line.allocations.map((a) => (
                <p className="mt-2 text-sm" key={a.id}>
                  {a.party_name} / {a.percentage}% /{" "}
                  {cash(a.amount, d.currency)}
                </p>
              ))}
              {!platform && d.status === "draft" && (
                <div className="mt-3 flex gap-2">
                  <button
                    className={secondaryButtonClass}
                    onClick={async () => {
                      await apiRequest(
                        "/api/royalties/lines/" + line.id + "/generate/",
                        { method: "POST" },
                      );
                      await load();
                    }}
                  >
                    Generate
                  </button>
                  <form
                    className="flex gap-2"
                    onSubmit={async (e) => {
                      e.preventDefault();
                      const element = e.currentTarget;
                      await apiRequest(
                        "/api/royalties/lines/" + line.id + "/allocations/",
                        {
                          method: "POST",
                          body: JSON.stringify(
                            Object.fromEntries(new FormData(element)),
                          ),
                        },
                      );
                      await load();
                    }}
                  >
                    <select className={fieldClass} name="party">
                      {parties.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.display_name}
                        </option>
                      ))}
                    </select>
                    <input
                      className={fieldClass}
                      name="percentage"
                      placeholder="%"
                    />
                    <input
                      className={fieldClass}
                      name="amount"
                      placeholder="Amount"
                    />
                    <button className={secondaryButtonClass}>Allocate</button>
                  </form>
                </div>
              )}
            </div>
          ))}
        </>
      )}
    </>
  );
  return platform ? <P>{b}</P> : <W>{b}</W>;
}
export function ArtistRightsPage() {
  const [d, setD] = useState<{
    allocations: {
      party: string;
      statement: string;
      currency: string;
      amount: string;
    }[];
  } | null>(null);
  useEffect(() => {
    void apiRequest<typeof d>("/api/artist-portal/rights/").then(setD);
  }, []);
  return (
    <RouteGuard portal="artist">
      <AppShell>
        <PageHeader
          eyebrow="Artist portal"
          title="My rights and earnings"
          description="Read-only finalized earnings directly linked to your Artist. This is not a payout record."
        />
        <div className="mt-7">
          {d?.allocations.map((i, n) => (
            <p
              className="mt-3 grid grid-cols-3 rounded-md border border-neutral-800 p-4"
              key={i.statement + n}
            >
              <strong>{i.party}</strong>
              <span>{i.statement}</span>
              <span>{cash(i.amount, i.currency)}</span>
            </p>
          ))}
          {d && !d.allocations.length && (
            <EmptyState
              title="No finalized allocations"
              detail="No finalized earnings are attributed to your linked Rights Party."
            />
          )}
        </div>
      </AppShell>
    </RouteGuard>
  );
}
