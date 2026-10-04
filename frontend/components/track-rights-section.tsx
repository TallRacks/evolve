"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api/client";
type Master = {
  id: string;
  party_name: string;
  ownership_percentage: string;
  territory_code: string;
};
type Work = { id: string; title: string; publishing_total: string };
type Party = { id: string; display_name: string };
export function TrackRightsSection({
  trackId,
  organizationId,
  platform = false,
}: {
  trackId: string;
  organizationId: string;
  platform?: boolean;
}) {
  const [masters, setMasters] = useState<Master[]>([]);
  const [works, setWorks] = useState<Work[]>([]);
  const [parties, setParties] = useState<Party[]>([]);
  useEffect(() => {
    if (organizationId)
      void Promise.all([
        apiRequest<Master[]>(
          "/api/rights/masters/?organization_id=" +
            organizationId +
            "&track=" +
            trackId,
        ),
        apiRequest<Work[]>(
          "/api/rights/works/?organization_id=" +
            organizationId +
            "&track=" +
            trackId,
        ),
        apiRequest<Party[]>(
          "/api/rights/parties/?organization_id=" + organizationId,
        ),
      ]).then((x) => {
        setMasters(x[0]);
        setWorks(x[1]);
        setParties(x[2]);
      });
  }, [trackId, organizationId]);
  const total = masters.reduce((n, x) => n + Number(x.ownership_percentage), 0);
  return (
    <section className="evolve-panel p-5">
      <h2 className="font-semibold">Rights</h2>
      <p className="mt-2 text-sm text-neutral-500">
        Master allocated {total}% / unallocated {Math.max(0, 100 - total)}%.
      </p>
      {masters.map((x) => (
        <p className="mt-3 border-t border-neutral-800 pt-3" key={x.id}>
          {x.party_name} / {x.ownership_percentage}% / {x.territory_code}
        </p>
      ))}
      {!platform && (
        <form
          className="mt-4 grid gap-2 sm:grid-cols-4"
          onSubmit={async (e) => {
            e.preventDefault();
            const element = e.currentTarget;
            await apiRequest("/api/rights/masters/", {
              method: "POST",
              body: JSON.stringify({
                ...Object.fromEntries(new FormData(element)),
                track: trackId,
              }),
            });
            element.reset();
            location.reload();
          }}
        >
          <select
            className="rounded-md border border-neutral-700 bg-neutral-950 p-2"
            name="party"
            required
          >
            {parties.map((x) => (
              <option key={x.id} value={x.id}>
                {x.display_name}
              </option>
            ))}
          </select>
          <input
            className="rounded-md border border-neutral-700 bg-neutral-950 p-2"
            name="ownership_percentage"
            type="number"
            step="0.0001"
            placeholder="Percent"
            required
          />
          <input
            className="rounded-md border border-neutral-700 bg-neutral-950 p-2"
            name="territory_code"
            defaultValue="WORLDWIDE"
          />
          <button className="rounded-md border border-neutral-700 px-3">
            Add master right
          </button>
        </form>
      )}
      <h3 className="mt-5 font-medium">Compositions</h3>
      {works.map((x) => (
        <Link
          className="mt-2 block text-sm"
          href={
            (platform ? "/platform" : "/workspace") + "/rights/works/" + x.id
          }
          key={x.id}
        >
          {x.title} / {x.publishing_total}% publishing
        </Link>
      ))}
      {!masters.length && !works.length && (
        <p className="mt-3 text-sm text-neutral-500">
          No Rights records linked.
        </p>
      )}
    </section>
  );
}
