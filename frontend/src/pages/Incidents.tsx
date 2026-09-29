import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { useMemo, useState } from "react";
import { useMedicineDrawer } from "../components/MedicineDrawer";
import { Badge, Card, EmptyState, ErrorState, inputBase, PageHeader, SegmentedControl, SkeletonRows } from "../components/ui";
import { api } from "../lib/api";
import { fmtDate, INCIDENT_TYPE } from "../lib/format";
import type { Incident } from "../lib/types";

const SEVERITY_TONE = { critical: "crit", high: "high", medium: "med", low: "neutral" } as const;

function MemoryStatus({ status }: { status: Incident["memory_status"] }) {
  if (status === "retained") return <Badge tone="memory">Retained</Badge>;
  if (status === "pending") return <Badge tone="med">Pending</Badge>;
  if (status === "failed") return <Badge tone="crit">Retain failed</Badge>;
  return <Badge>Not retained</Badge>;
}

export default function Incidents() {
  const drawer = useMedicineDrawer();
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["incidents"], queryFn: api.incidents });
  const [status, setStatus] = useState<"ALL" | "OPEN" | "RESOLVED">("ALL");
  const [type, setType] = useState("ALL");
  const rows = useMemo(
    () =>
      (data ?? []).filter(
        (i) =>
          (status === "ALL" || (status === "OPEN" ? i.status !== "resolved" : i.status === "resolved")) &&
          (type === "ALL" || i.type === type),
      ),
    [data, status, type],
  );
  const openCount = (data ?? []).filter((i) => i.status !== "resolved").length;
  return (
    <>
      <PageHeader title="Incidents" subtitle="Stock-outs, supplier delays, expiry risks and demand spikes — and whether each became operational memory." />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <SegmentedControl
          value={status}
          onChange={setStatus}
          options={[
            { value: "ALL", label: "All", count: data?.length ?? 0 },
            { value: "OPEN", label: "Open", count: openCount },
            { value: "RESOLVED", label: "Resolved", count: (data?.length ?? 0) - openCount },
          ]}
        />
        <select className={clsx(inputBase, "w-56")} value={type} onChange={(e) => setType(e.target.value)} aria-label="Incident type">
          <option value="ALL">All incident types</option>
          {Object.entries(INCIDENT_TYPE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      {error && !data ? <ErrorState error={error} onRetry={() => refetch()} /> : (
      <Card className="overflow-hidden">
        {isLoading ? <SkeletonRows rows={8} /> : rows.length === 0 ? <EmptyState title="No incidents match these filters" /> : (
          <div className="thin-scroll overflow-x-auto">
            <table className="w-full min-w-[1150px] text-[13px]">
              <thead className="border-b border-line bg-canvas/80 text-left text-[11.5px] text-muted">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Incident</th>
                  <th className="px-3 py-2.5 font-medium">Date</th>
                  <th className="px-3 py-2.5 font-medium">Severity</th>
                  <th className="px-3 py-2.5 font-medium">Cause</th>
                  <th className="px-3 py-2.5 font-medium">Action</th>
                  <th className="px-3 py-2.5 font-medium">Supplier</th>
                  <th className="px-3 py-2.5 font-medium">Outcome</th>
                  <th className="px-3 py-2.5 pr-4 font-medium">Memory</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line align-top">
                {rows.map((i) => (
                  <tr key={i.id} className="hover:bg-canvas/60">
                    <td className="px-4 py-3">
                      <button onClick={() => drawer.open(i.medicine_id)} className="text-left font-medium text-ink hover:text-brand-700">{i.title}</button>
                      <div className="text-[11.5px] text-muted">{i.id} · {INCIDENT_TYPE[i.type]} · {i.medicine_name}</div>
                      {i.status !== "resolved" && <Badge tone="high" className="mt-1">{i.status === "open" ? "Open" : "Monitoring"}</Badge>}
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap text-ink-2">{fmtDate(i.occurred_at)}</td>
                    <td className="px-3 py-3"><Badge tone={SEVERITY_TONE[i.severity]}>{i.severity}</Badge></td>
                    <td className="max-w-[240px] px-3 py-3 text-ink-2">{i.cause}</td>
                    <td className="max-w-[220px] px-3 py-3 text-ink-2">{i.action}</td>
                    <td className="px-3 py-3 whitespace-nowrap text-ink-2">{i.supplier_name ?? "—"}</td>
                    <td className="max-w-[200px] px-3 py-3 text-ink-2">{i.outcome}</td>
                    <td className="px-3 py-3 pr-4"><MemoryStatus status={i.memory_status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      )}
    </>
  );
}
