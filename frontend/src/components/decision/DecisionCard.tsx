import { useMutation } from "@tanstack/react-query";
import { clsx } from "clsx";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { fmtDate, fmtDateTime, fmtDays, fmtRelative, MEMORY_CATEGORY, TOOL_LABEL } from "../../lib/format";
import { useRefreshAll, useRefreshMemory } from "../../lib/hooks";
import type { Decision } from "../../lib/types";
import { Badge, Button, RiskBadge, riskTone } from "../ui";
import { useMedicineDrawer } from "../MedicineDrawer";
import { ApproveDialog, OutcomeDialog, RejectDialog } from "./DecisionDialogs";

const STATUS_TONE = {
  pending: "high",
  approved: "brand",
  completed: "ok",
  rejected: "neutral",
  superseded: "neutral",
} as const;
const STATUS_LABEL = {
  pending: "Awaiting approval",
  approved: "Approved · awaiting outcome",
  completed: "Completed",
  rejected: "Rejected",
  superseded: "Superseded",
};

export function DecisionStatusBadge({ status }: { status: Decision["status"] }) {
  return <Badge tone={STATUS_TONE[status]}>{STATUS_LABEL[status]}</Badge>;
}

export function EngineBadge({ engine }: { engine: string }) {
  if (engine === "manual") return <Badge>Manual decision</Badge>;
  if (engine === "rules")
    return (
      <Badge tone="med" className="font-normal">
        Rules-based · AI model unavailable
      </Badge>
    );
  return null;
}

export function Timeline({ decision }: { decision: Decision }) {
  const steps = decision.timeline ?? [];
  const firstOpen = steps.findIndex((s) => !s.done);
  return (
    <ol className="flex flex-wrap items-center gap-y-2">
      {steps.map((step, i) => {
        const current = i === firstOpen;
        return (
          <li key={step.key} className="flex items-center">
            <div
              className={clsx(
                "flex items-center gap-1.5 rounded-full px-2 py-1 text-[12px] font-medium",
                step.done && step.key === "recalled" && "bg-memory-50 text-memory-700",
                step.done && step.key === "retained" && "bg-memory-50 text-memory-700",
                step.done && !["recalled", "retained"].includes(step.key) && "text-ink-2",
                step.key === "rejected" && "bg-canvas text-ink-2",
                current && "bg-high-50 text-high-700 ring-1 ring-high-200",
                !step.done && !current && "text-faint",
              )}
              title={step.detail ?? (step.at ? fmtDateTime(step.at) : undefined)}
            >
              <span
                className={clsx(
                  "size-2 shrink-0 rounded-full",
                  step.done && (step.key === "recalled" || step.key === "retained") && "bg-memory-500",
                  step.done && step.key === "rejected" && "bg-faint",
                  step.done && !["recalled", "retained", "rejected"].includes(step.key) && "bg-ok-600",
                  current && "animate-pulse-dot bg-high-600",
                  !step.done && !current && "border border-line-strong",
                )}
              />
              {step.label}
            </div>
            {i < steps.length - 1 && <span className="mx-1 h-px w-3 bg-line-strong" />}
          </li>
        );
      })}
    </ol>
  );
}

function Fact({ label, value, sub, tone }: { label: string; value: React.ReactNode; sub?: string; tone?: string }) {
  return (
    <div className="px-4 py-3">
      <div className="text-[11px] font-medium tracking-wide text-muted uppercase">{label}</div>
      <div className={clsx("mt-1 text-[18px] font-semibold tabular", tone ?? "text-ink")}>{value}</div>
      {sub && <div className="text-[12px] text-muted">{sub}</div>}
    </div>
  );
}

function Comparison({ decision }: { decision: Decision }) {
  const b = decision.baseline;
  if (!b) return null;
  const changed = b.supplier_id !== decision.recommended_supplier_id;
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <div className="rounded-lg border border-line bg-canvas/60 p-4">
        <div className="flex items-center justify-between">
          <div className="text-[11.5px] font-semibold tracking-wider text-muted uppercase">Without operational memory</div>
          <Badge>Current data only</Badge>
        </div>
        <div className="mt-2.5 text-[14px] font-semibold text-ink-2">{b.headline}</div>
        <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{b.reason}</p>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] text-ink-2">
          <span>{b.supplier_name}</span>
          <span className="tabular">{b.quantity} units</span>
          <span className="tabular">Assumed lead {fmtDays(b.lead_days)} days</span>
        </div>
      </div>
      <div className="relative rounded-lg border border-memory-200 bg-memory-50/50 p-4 ring-1 ring-memory-100">
        <div className="flex items-center justify-between">
          <div className="text-[11.5px] font-semibold tracking-wider text-memory-700 uppercase">With operational memory</div>
          {changed ? <Badge tone="memory">Memory changed the supplier</Badge> : decision.memory_used.length > 0 ? <Badge tone="memory">Memory confirmed choice</Badge> : null}
        </div>
        <div className="mt-2.5 text-[14px] font-semibold text-ink">{decision.headline}</div>
        <p className="mt-1.5 text-[13px] leading-relaxed text-ink-2">{decision.reason}</p>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] text-ink">
          <span className="font-medium">{decision.recommended_supplier_name}</span>
          <span className="tabular">{decision.recommended_quantity} units</span>
          <span className="tabular">Expected lead {fmtDays(decision.planning_lead_days)} days</span>
        </div>
      </div>
    </div>
  );
}

function MemoryEvidence({ decision }: { decision: Decision }) {
  const [showAll, setShowAll] = useState(false);
  const usedIds = new Set(decision.memory_used.map((m) => m.memory_id));
  const others = decision.memories_recalled.filter((m) => !usedIds.has(m.id));
  if (decision.memory_state === "unavailable") {
    return (
      <div className="rounded-lg border border-med-200 bg-med-50 px-3 py-2.5 text-[12.5px] text-med-700">
        Hindsight was unavailable during this analysis, so no operational memory was used. Re-run the analysis once Hindsight is connected.
      </div>
    );
  }
  if (decision.memory_used.length === 0) {
    return (
      <div className="rounded-lg border border-line bg-canvas/60 px-3 py-2.5 text-[12.5px] text-muted">
        {decision.memories_recalled.length
          ? `${decision.memories_recalled.length} memories were recalled but none changed this recommendation.`
          : "No relevant operational memory exists for this medicine yet."}
      </div>
    );
  }
  return (
    <div className="space-y-2">
      {decision.memory_used.map((m) => (
        <div key={m.memory_id} className="rounded-lg border border-memory-200 bg-surface px-3 py-2.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5">
              <span className="rounded bg-memory-600 px-1.5 py-px font-mono text-[10.5px] font-semibold text-white">{m.ref}</span>
              <span className="text-[11.5px] font-medium text-memory-700">{MEMORY_CATEGORY[m.category] ?? m.category}</span>
            </div>
            <span className="text-[11px] text-muted">{m.occurred ? fmtDate(m.occurred) : ""}</span>
          </div>
          <p className="mt-1.5 text-[12.5px] leading-relaxed text-ink">{m.text}</p>
          {m.experience && (
            <p className="mt-1 text-[12px] text-ink-2">
              <span className="font-medium">Recorded delivery:</span> {m.experience}
            </p>
          )}
          {m.influence && (
            <p className="mt-1.5 text-[12px] text-memory-700">
              <span className="font-medium">Effect on decision:</span> {m.influence}
            </p>
          )}
          <div className="mt-1.5 text-[10.5px] text-faint" title={`Hindsight document ${m.document_id ?? ""}`}>Historical experience · recalled from Hindsight</div>
        </div>
      ))}
      {others.length > 0 && (
        <button onClick={() => setShowAll((v) => !v)} className="flex items-center gap-1 text-[12px] font-medium text-memory-700 hover:underline">
          <ChevronDown className={clsx("size-3.5 transition-transform", showAll && "rotate-180")} />
          {showAll ? "Hide" : "Show"} {others.length} other recalled {others.length === 1 ? "memory" : "memories"}
        </button>
      )}
      {showAll &&
        others.map((m) => (
          <div key={m.id} className="rounded-md border border-line bg-canvas/50 px-3 py-2 text-[12px] text-ink-2">
            <span className="mr-1.5 font-mono text-[10.5px] text-muted">{m.ref}</span>
            {m.text}
          </div>
        ))}
    </div>
  );
}

function AgentTrace({ decision }: { decision: Decision }) {
  const [open, setOpen] = useState(false);
  if (!decision.trace.length) return null;
  return (
    <div>
      <button onClick={() => setOpen((v) => !v)} className="flex items-center gap-1 text-[12px] font-medium text-muted hover:text-ink">
        <ChevronDown className={clsx("size-3.5 transition-transform", open && "rotate-180")} />
        How the agent investigated · {decision.trace.length} steps · {(decision.trace.reduce((a, s) => a + s.duration_ms, 0) / 1000).toFixed(1)} s
      </button>
      {open && (
        <div className="mt-2 overflow-hidden rounded-lg border border-line">
          {decision.trace.map((s, i) => (
            <div key={i} className={clsx("grid grid-cols-[22px_250px_1fr_70px] items-start gap-2 px-3 py-2 text-[12px]", i % 2 && "bg-canvas/60")}>
              <span className={clsx("mt-0.5 size-2 rounded-full", s.status === "ok" ? "bg-ok-600" : "bg-crit-600", s.tool === "recall_hindsight_memory" && s.status === "ok" && "bg-memory-500")} />
              <span className={clsx("font-mono text-[11.5px]", s.tool === "recall_hindsight_memory" ? "text-memory-700" : "text-ink-2")}>{TOOL_LABEL[s.tool] ?? s.tool}</span>
              <span className="text-ink-2">{s.summary}</span>
              <span className="text-right text-muted tabular">{s.duration_ms} ms</span>
            </div>
          ))}
          {decision.recall_query && (
            <div className="border-t border-line bg-memory-50/40 px-3 py-2 text-[11.5px] text-memory-700">
              <span className="font-medium">Hindsight recall query:</span> {decision.recall_query}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function OutcomePanel({ decision }: { decision: Decision }) {
  const refresh = useRefreshAll();
  const refreshMemory = useRefreshMemory();
  const retry = useMutation({
    mutationFn: () => api.retryRetain(decision.id),
    onSuccess: () => {
      toast.success("Experience retained in Hindsight");
      refresh();
      refreshMemory();
    },
    onError: (e: Error) => toast.error("Retain failed", { description: e.message }),
  });
  const o = decision.outcome;
  if (!o) return null;
  const tone = o.result === "successful" ? "ok" : o.result === "delayed" ? "med" : "crit";
  return (
    <div className="grid gap-3 md:grid-cols-[1fr_1fr]">
      <div className="rounded-lg border border-line p-3.5">
        <div className="flex items-center justify-between">
          <div className="text-[11.5px] font-semibold tracking-wider text-muted uppercase">Delivery outcome</div>
          <Badge tone={tone}>{o.result.toUpperCase()}</Badge>
        </div>
        <div className="mt-2 grid grid-cols-3 gap-2 text-[12.5px]">
          <div><div className="text-muted">Delivered</div><div className="font-semibold tabular">{o.delivered_quantity} units</div></div>
          <div><div className="text-muted">Delivery time</div><div className="font-semibold tabular">{fmtDays(o.delivery_days)} days</div></div>
          <div><div className="text-muted">Stock-out</div><div className={clsx("font-semibold", o.stockout.startsWith("avoided") ? "text-ok-700" : "text-crit-700")}>{o.stockout.startsWith("avoided") ? "Avoided" : o.stockout === "near" ? "Near miss" : "Occurred"}</div></div>
        </div>
        <p className="mt-2 text-[12px] text-muted">{o.summary}</p>
      </div>
      {decision.retained_document_id ? (
        <div className="rounded-lg border border-memory-200 bg-memory-50/60 p-3.5">
          <div>
            <div className="text-[11px] font-semibold tracking-wider text-memory-700 uppercase">Operational learning</div>
            <div className="mt-0.5 text-[13px] font-semibold text-memory-700">Experience added to operational memory</div>
            <div className="mt-0.5 text-[12px] text-ink-2">
              The situation, decision, delivery performance and outcome were retained in Hindsight. Future {decision.generic_name} decisions will recall this experience.
            </div>
          </div>
        </div>
      ) : decision.source === "agent" ? (
        <div className="flex items-start justify-between gap-3 rounded-lg border border-crit-200 bg-crit-50 p-3.5">
          <div className="text-[12.5px] text-crit-700">The outcome is saved, but it could not be retained in Hindsight, so future decisions will not learn from it until it is retried.</div>
          <Button size="sm" loading={retry.isPending} onClick={() => retry.mutate()}>Retry retain</Button>
        </div>
      ) : null}
    </div>
  );
}

export default function DecisionCard({ decision, highlight, readOnly }: { decision: Decision; highlight?: boolean; readOnly?: boolean }) {
  const [dialog, setDialog] = useState<null | "approve" | "modify" | "reject" | "outcome">(null);
  const drawer = useMedicineDrawer();
  const d = decision;
  const coverTone = riskTone(d.risk_level) === "crit" ? "text-crit-700" : riskTone(d.risk_level) === "high" ? "text-high-700" : "text-ink";
  return (
    <div className={clsx("overflow-hidden rounded-xl border bg-surface", highlight ? "border-memory-200 ring-2 ring-memory-100" : "border-line")}>
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-line px-5 py-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={() => drawer.open(d.medicine_id)} className="text-[15px] font-semibold tracking-wide text-ink uppercase hover:text-brand-700">
              {d.medicine_name}
            </button>
            <RiskBadge level={d.risk_level} />
            <span className="text-[12px] font-medium text-muted uppercase">stock-out risk</span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-[12px] text-muted">
            <span className="font-mono">{d.id}</span>·<span>{fmtRelative(d.created_at)}</span>·<DecisionStatusBadge status={d.status} />
            <EngineBadge engine={d.engine} />
          </div>
        </div>
        <div className={clsx("flex items-center gap-2", readOnly && "hidden")}>
          {d.status === "pending" && (
            <>
              <Button variant="primary" onClick={() => setDialog("approve")}>Approve</Button>
              <Button onClick={() => setDialog("modify")}>Modify</Button>
              <Button variant="danger" onClick={() => setDialog("reject")}>Reject</Button>
            </>
          )}
          {d.status === "approved" && (
            <Button variant="memory" onClick={() => setDialog("outcome")}>Record outcome</Button>
          )}
        </div>
      </div>

      {/* Current operational data (system of record) */}
      <div className="bg-canvas/50 px-5 pt-3 text-[10.5px] font-semibold tracking-wider text-muted uppercase">
        Current operational data
      </div>
      <div className="grid grid-cols-2 divide-x divide-line border-b border-line bg-canvas/50 md:grid-cols-5">
        <Fact label="Current stock" value={`${d.current_stock} units`} />
        <Fact label="Estimated remaining" value={`${fmtDays(d.days_remaining)} days`} tone={coverTone} />
        <Fact label="Demand" value={`${fmtDays(d.daily_demand)}/day`} />
        <Fact label="Primary supplier" value={d.primary_supplier_name} />
        <Fact label="Assessment" value={<span className="text-[13px] leading-snug font-medium">{d.assessment || "—"}</span>} />
      </div>

      <div className="space-y-5 px-5 py-4">
        {/* Recommendation strip */}
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg bg-brand-50/70 px-4 py-3 ring-1 ring-brand-100">
          <span className="text-[11.5px] font-semibold tracking-wider text-brand-700 uppercase">Recommendation</span>
          <span className="text-[14px] font-semibold text-ink">{d.headline}</span>
          <div className="ml-auto flex flex-wrap items-center gap-x-5 gap-y-1 text-[12.5px] text-ink-2">
            <span>Supplier <b className="text-ink">{d.final_supplier_name ?? d.recommended_supplier_name}</b></span>
            <span className="tabular">Quantity <b className="text-ink">{d.final_quantity ?? d.recommended_quantity} units</b></span>
            <span>Urgency <b className="text-ink capitalize">{d.urgency}</b></span>
            <span>Confidence <b className="text-ink capitalize">{d.confidence}</b></span>
          </div>
        </div>
        {d.status === "pending" && d.planning_lead_days >= d.days_remaining && (
          <div className="-mt-3 rounded-md border border-crit-200 bg-crit-50 px-3 py-2 text-[12.5px] text-crit-700">
            Expected delivery ({fmtDays(d.planning_lead_days)} days) lands after the projected stock-out ({fmtDays(d.days_remaining)} days)
            — no approved supplier can arrive in time, so plan interim cover such as a sister-store transfer.
          </div>
        )}
        {d.final_supplier_id && (d.final_supplier_id !== d.recommended_supplier_id || d.final_quantity !== d.recommended_quantity) && (
          <div className="-mt-3 text-[12px] text-muted">
            Manager modified the recommendation ({d.recommended_quantity} units from {d.recommended_supplier_name})
            {d.manager_note ? ` — “${d.manager_note}”` : ""}.
          </div>
        )}
        {d.status === "rejected" && d.manager_note && (
          <div className="-mt-3 text-[12px] text-muted">Rejected by manager — “{d.manager_note}”</div>
        )}

        <Comparison decision={d} />

        <div className="grid gap-5 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          <div>
            <div className="mb-2 text-[12.5px] font-semibold text-ink">Why this recommendation?</div>
            <ul className="space-y-1.5">
              {d.why.map((w, i) => (
                <li key={i} className="flex gap-2 text-[13px] text-ink-2">
                  <span className="mt-[7px] size-1.5 shrink-0 rounded-full bg-brand-500" />
                  {w}
                </li>
              ))}
            </ul>
            {d.alternatives.length > 0 && (
              <div className="mt-4">
                <div className="mb-1.5 text-[12px] font-medium text-muted">Alternatives considered</div>
                {d.alternatives.map((a) => (
                  <div key={a.supplier_id} className="text-[12.5px] text-ink-2">
                    <span className="font-medium">{a.supplier_name}</span> — {a.why_not}
                  </div>
                ))}
              </div>
            )}
          </div>
          <div>
            <div className="mb-2 flex items-center justify-between">
              <div className="text-[12.5px] font-semibold text-memory-700">Memory used</div>
              <span className="text-[11.5px] text-muted">
                {d.memory_used.length} of {d.memories_recalled.length} recalled experiences
              </span>
            </div>
            <MemoryEvidence decision={d} />
          </div>
        </div>

        <OutcomePanel decision={d} />

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
          <Timeline decision={d} />
        </div>
        <AgentTrace decision={d} />
      </div>

      <ApproveDialog decision={d} mode="approve" open={dialog === "approve"} onClose={() => setDialog(null)} />
      <ApproveDialog decision={d} mode="modify" open={dialog === "modify"} onClose={() => setDialog(null)} />
      <RejectDialog decision={d} open={dialog === "reject"} onClose={() => setDialog(null)} />
      <OutcomeDialog decision={d} open={dialog === "outcome"} onClose={() => setDialog(null)} />
    </div>
  );
}
