import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import DecisionCard, { DecisionStatusBadge } from "../components/decision/DecisionCard";
import { useMedicineDrawer } from "../components/MedicineDrawer";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, PageHeader, RiskBadge, Skeleton } from "../components/ui";
import { api } from "../lib/api";
import { fmtDays, fmtRelative } from "../lib/format";
import { useRefreshAll } from "../lib/hooks";

export function AnalysingBanner({ name }: { name: string }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-memory-200 bg-memory-50/60 px-5 py-4">
      <Loader2 className="size-4 animate-spin text-memory-600" />
      <div>
        <div className="text-[13.5px] font-semibold text-ink">Agent analysing {name}</div>
        <div className="text-[12.5px] text-muted">
          Inspecting inventory → calculating risk → checking supplier terms → recalling Hindsight memory → generating and validating the recommendation
        </div>
      </div>
    </div>
  );
}

export default function AgentDecisions() {
  const refresh = useRefreshAll();
  const drawer = useMedicineDrawer();
  const [running, setRunning] = useState<{ id: string; name: string } | null>(null);
  const decisions = useQuery({ queryKey: ["decisions", "active"], queryFn: () => api.decisions("pending,approved"), refetchInterval: 10000 });
  const recent = useQuery({ queryKey: ["decisions", "recent"], queryFn: () => api.decisions("completed,rejected") });
  const inventory = useQuery({ queryKey: ["inventory"], queryFn: api.inventory });

  const analyze = useMutation({
    mutationFn: (m: { id: string; name: string }) => {
      setRunning(m);
      return api.analyze(m.id);
    },
    onSuccess: (d) => {
      toast.success(`Recommendation ready for ${d.medicine_name}`, { description: `${d.headline} · ${d.memory_used.length} Hindsight memories cited` });
      refresh();
    },
    onError: (e: Error) => toast.error("Analysis failed", { description: e.message }),
    onSettled: () => setRunning(null),
  });

  const queue = (inventory.data ?? [])
    .filter((m) => (m.risk_level === "CRITICAL" || m.risk_level === "HIGH") && !m.active_decision_id)
    .sort((a, b) => a.days_remaining - b.days_remaining);
  const pending = (decisions.data ?? []).filter((d) => d.status === "pending");
  const approved = (decisions.data ?? []).filter((d) => d.status === "approved");

  return (
    <>
      <PageHeader
        title="Agent Decision Center"
        subtitle="Replenishment recommendations grounded in current inventory and the pharmacy's operational memory."
      />

      {queue.length > 0 && (
        <Card className="mb-5">
          <CardHeader
            title="Flagged by risk scan — awaiting agent analysis"
            subtitle="High and critical stock-out risks without an active decision"
          />
          <div className="divide-y divide-line">
            {queue.map((m) => (
              <div key={m.id} className="flex items-center gap-4 px-4 py-2.5">
                <button onClick={() => drawer.open(m.id)} className="min-w-0 flex-1 text-left">
                  <div className="text-[13px] font-medium hover:text-brand-700">{m.name}</div>
                  <div className="text-[12px] text-muted tabular">{m.current_stock} units · {fmtDays(m.daily_demand)}/day · primary {m.primary_supplier_name}</div>
                </button>
                <RiskBadge level={m.risk_level} />
                <span className="w-20 text-right text-[13px] font-semibold tabular">{fmtDays(m.days_remaining)} days</span>
                <Button
                  size="sm"
                  variant="primary"
                  loading={running?.id === m.id}
                  disabled={!!running}
                  onClick={() => analyze.mutate({ id: m.id, name: m.name })}
                >
                  Analyze
                </Button>
              </div>
            ))}
          </div>
        </Card>
      )}

      {running && <div className="mb-5"><AnalysingBanner name={running.name} /></div>}
      {decisions.error && <ErrorState error={decisions.error} onRetry={() => decisions.refetch()} />}

      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-[12px] font-semibold tracking-wider text-muted uppercase">Requires your decision · {pending.length}</h2>
      </div>
      {decisions.error && !decisions.data ? null : decisions.isLoading ? (
        <Skeleton className="h-[420px]" />
      ) : pending.length === 0 ? (
        <Card>
          <EmptyState
            title="No recommendations awaiting approval"
            description={queue.length ? "Run an agent analysis on a flagged medicine above." : "All high-risk medicines have an active decision."}
          />
        </Card>
      ) : (
        <div className="space-y-5">
          {pending.map((d) => <DecisionCard key={d.id} decision={d} highlight={d.memory_used.length > 0} />)}
        </div>
      )}

      {approved.length > 0 && (
        <>
          <h2 className="mt-8 mb-3 text-[12px] font-semibold tracking-wider text-muted uppercase">Approved · awaiting delivery outcome · {approved.length}</h2>
          <div className="space-y-5">
            {approved.map((d) => <DecisionCard key={d.id} decision={d} />)}
          </div>
        </>
      )}

      <Card className="mt-8">
        <CardHeader title="Recently closed" subtitle="Completed and rejected decisions" action={<Link to="/decisions" className="text-[12px] font-medium text-brand-700">Full history</Link>} />
        {recent.isLoading ? <Skeleton className="m-4 h-24" /> : !recent.data?.length ? <EmptyState title="Nothing closed yet" /> : (
          <div className="divide-y divide-line">
            {recent.data.slice(0, 6).map((d) => (
              <div key={d.id} className="flex items-center gap-4 px-4 py-2.5 text-[13px]">
                <span className="w-20 font-mono text-[12px] text-muted">{d.id}</span>
                <span className="w-56 truncate font-medium">{d.medicine_name}</span>
                <span className="flex-1 truncate text-ink-2">{d.final_supplier_name ?? d.recommended_supplier_name} · {d.final_quantity ?? d.recommended_quantity} units{d.outcome ? ` · ${d.outcome.summary}` : ""}</span>
                {d.retained_document_id && <Badge tone="memory">Retained</Badge>}
                <DecisionStatusBadge status={d.status} />
                <span className="w-24 text-right text-[12px] text-muted">{fmtRelative(d.outcome_at ?? d.rejected_at ?? d.created_at)}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}
