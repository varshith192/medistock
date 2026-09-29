import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { useMemo, useState } from "react";
import DecisionCard, { DecisionStatusBadge, EngineBadge } from "../components/decision/DecisionCard";
import { Badge, Card, CardHeader, Drawer, EmptyState, ErrorState, inputBase, PageHeader, SkeletonRows } from "../components/ui";
import { api } from "../lib/api";
import { fmtDays, fmtShortDate } from "../lib/format";
import type { Decision } from "../lib/types";

function outcomeTone(d: Decision) {
  if (!d.outcome) return "neutral" as const;
  return d.outcome.result === "successful" ? ("ok" as const) : d.outcome.result === "delayed" ? ("med" as const) : ("crit" as const);
}

function LearningCurve({ decisions }: { decisions: Decision[] }) {
  const amox = decisions.filter((d) => d.medicine_id === "MED-001" && d.status !== "superseded").sort((a, b) => a.created_at.localeCompare(b.created_at));
  if (amox.length < 2) return null;
  return (
    <Card className="mb-5">
      <CardHeader
        title="Learning curve — Amoxicillin 500mg"
        subtitle="How each outcome became memory and changed the next replenishment decision"
      />
      <div className="thin-scroll flex gap-0 overflow-x-auto px-4 py-4">
        {amox.map((d, i) => (
          <div key={d.id} className="flex items-stretch">
            <div className={clsx("w-[230px] shrink-0 rounded-lg border p-3", d.memory_used.length ? "border-memory-200 bg-memory-50/50" : "border-line")}>
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-semibold">{fmtShortDate(d.created_at)}</span>
                {d.outcome ? <Badge tone={outcomeTone(d)}>{d.outcome.result}</Badge> : <DecisionStatusBadge status={d.status} />}
              </div>
              <div className="mt-1.5 text-[13px] font-medium text-ink">{d.final_supplier_name ?? d.recommended_supplier_name}</div>
              <div className="text-[12px] text-muted"><span className="capitalize">{d.urgency}</span> reorder · {d.final_quantity ?? d.recommended_quantity} units</div>
              <div className="mt-2 text-[12px] text-ink-2">
                {d.source === "manual" ? "Manual decision (before agent)" : d.memory_used.length ? (
                  <span className="flex items-start gap-1 text-memory-700">Recommended based on {d.memory_used.length} recalled {d.memory_used.length === 1 ? "experience" : "experiences"}</span>
                ) : "Agent recommendation"}
              </div>
              {d.outcome && <div className="mt-1 text-[11.5px] text-muted">Delivered in {fmtDays(d.outcome.delivery_days)} days</div>}
            </div>
            {i < amox.length - 1 && (
              <div className="flex w-10 shrink-0 flex-col items-center justify-center text-memory-600">
                <div className="h-px w-full bg-memory-200" />
                {amox[i].retained_document_id && <span className="my-1 text-[10px] font-medium text-memory-600">learned</span>}
                <div className="h-px w-full bg-memory-200" />
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function DecisionHistory() {
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["decisions", "all"], queryFn: () => api.decisions() });
  const [medicine, setMedicine] = useState("ALL");
  const [selected, setSelected] = useState<Decision | null>(null);
  const visible = useMemo(() => (data ?? []).filter((d) => d.status !== "superseded" && (medicine === "ALL" || d.medicine_id === medicine)), [data, medicine]);
  const medicines = useMemo(() => Array.from(new Map((data ?? []).map((d) => [d.medicine_id, d.medicine_name])).entries()), [data]);

  return (
    <>
      <PageHeader title="Decisions" subtitle="Every replenishment decision, why it was made, and what happened afterwards." />
      {error && <ErrorState error={error} onRetry={() => refetch()} />}
      {data && <LearningCurve decisions={data} />}
      <div className="mb-3 flex items-center gap-2">
        <select className={clsx(inputBase, "w-64")} value={medicine} onChange={(e) => setMedicine(e.target.value)} aria-label="Medicine">
          <option value="ALL">All medicines</option>
          {medicines.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
        <span className="text-[12.5px] text-muted">{visible.length} decisions</span>
      </div>
      <Card className="overflow-hidden">
        {isLoading ? <SkeletonRows rows={8} /> : error ? <EmptyState title="Decisions could not be loaded" /> : visible.length === 0 ? <EmptyState title="No decisions yet" /> : (
          <table className="w-full text-[13px]">
            <thead className="border-b border-line bg-canvas/80 text-left text-[11.5px] text-muted">
              <tr>
                <th className="px-4 py-2.5 font-medium">Date</th>
                <th className="px-3 py-2.5 font-medium">Medicine</th>
                <th className="px-3 py-2.5 font-medium">Supplier</th>
                <th className="px-3 py-2.5 font-medium">Decision</th>
                <th className="px-3 py-2.5 font-medium">Memory</th>
                <th className="px-3 py-2.5 font-medium">Outcome</th>
                <th className="px-3 py-2.5 pr-4 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {visible.map((d) => (
                <tr key={d.id} className="cursor-pointer hover:bg-canvas/70" onClick={() => setSelected(d)}>
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    <div className="font-medium">{fmtShortDate(d.created_at)}</div>
                    <div className="font-mono text-[11px] text-muted">{d.id}</div>
                  </td>
                  <td className="px-3 font-medium">{d.medicine_name}</td>
                  <td className="px-3 text-ink-2">{d.final_supplier_name ?? d.recommended_supplier_name}</td>
                  <td className="max-w-[340px] px-3">
                    <div className="truncate text-ink-2">{d.headline}</div>
                    <div className="mt-0.5"><EngineBadge engine={d.engine} /></div>
                  </td>
                  <td className="px-3">
                    {d.source === "manual" ? <span className="text-[12px] text-muted">—</span> : d.memory_used.length ? (
                      <Badge tone="memory">{d.memory_used.length} used</Badge>
                    ) : <span className="text-[12px] text-muted">None</span>}
                  </td>
                  <td className="px-3">{d.outcome ? <Badge tone={outcomeTone(d)}>{d.outcome.result}</Badge> : <span className="text-[12px] text-muted">—</span>}</td>
                  <td className="px-3 pr-4"><DecisionStatusBadge status={d.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      <Drawer open={!!selected} onClose={() => setSelected(null)} title={selected ? `${selected.id} · ${selected.medicine_name}` : ""} subtitle="Decision record" width="max-w-[980px]">
        {selected && <DecisionCard decision={data?.find((d) => d.id === selected.id) ?? selected} />}
      </Drawer>
    </>
  );
}
