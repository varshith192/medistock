import { useMutation, useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { Bar, BarChart, CartesianGrid, ComposedChart, Area, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";
import { api } from "../lib/api";
import { fmtDate, fmtDays, fmtShortDate, INCIDENT_TYPE, MEMORY_CATEGORY } from "../lib/format";
import { useRefreshAll } from "../lib/hooks";
import type { MedicineDetail } from "../lib/types";
import DecisionCard, { DecisionStatusBadge } from "./decision/DecisionCard";
import ErrorBoundary from "./ErrorBoundary";
import { Badge, Button, Card, CardHeader, Drawer, EmptyState, ErrorState, RiskBadge, Skeleton } from "./ui";

interface DrawerCtx {
  open: (medicineId: string) => void;
}
const Ctx = createContext<DrawerCtx>({ open: () => undefined });
export const useMedicineDrawer = () => useContext(Ctx);

export function MedicineDrawerProvider({ children }: { children: ReactNode }) {
  const [medicineId, setMedicineId] = useState<string | null>(null);
  const open = useCallback((id: string) => setMedicineId(id), []);
  const value = useMemo(() => ({ open }), [open]);
  return (
    <Ctx.Provider value={value}>
      {children}
      {medicineId && (
        <ErrorBoundary key={medicineId}>
          <MedicineDrawer medicineId={medicineId} onClose={() => setMedicineId(null)} />
        </ErrorBoundary>
      )}
    </Ctx.Provider>
  );
}

const tooltipStyle = { fontSize: 12, borderRadius: 8, border: "1px solid #e4e7ec", boxShadow: "0 4px 12px rgba(16,24,40,.08)" };

function StockChart({ detail }: { detail: MedicineDetail }) {
  const data = [
    ...detail.history.map((h) => ({ day: fmtShortDate(h.day), stock: h.closing_stock, received: h.received || null })),
    { day: "Today", stock: detail.medicine.current_stock, received: null },
  ];
  const safety = Math.round(detail.medicine.daily_demand * 4);
  return (
    <ResponsiveContainer width="100%" height={190}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
        <CartesianGrid stroke="#eef0f3" vertical={false} />
        <XAxis dataKey="day" tick={{ fontSize: 11, fill: "#98a2b3" }} tickLine={false} axisLine={false} interval={4} />
        <YAxis tick={{ fontSize: 11, fill: "#98a2b3" }} tickLine={false} axisLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <ReferenceLine y={safety} stroke="#e0590d" strokeDasharray="4 4" label={{ value: "4-day cover", fontSize: 10, fill: "#b93815", position: "insideTopRight" }} />
        <Bar dataKey="received" name="Received" fill="#a9d7d2" barSize={8} radius={[2, 2, 0, 0]} />
        <Area type="monotone" dataKey="stock" name="Closing stock" stroke="#0f6c64" strokeWidth={2} fill="#0f6c64" fillOpacity={0.08} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function DemandChart({ detail }: { detail: MedicineDetail }) {
  const data = detail.history.map((h) => ({ day: fmtShortDate(h.day), dispensed: h.dispensed }));
  return (
    <ResponsiveContainer width="100%" height={190}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
        <CartesianGrid stroke="#eef0f3" vertical={false} />
        <XAxis dataKey="day" tick={{ fontSize: 11, fill: "#98a2b3" }} tickLine={false} axisLine={false} interval={4} />
        <YAxis tick={{ fontSize: 11, fill: "#98a2b3" }} tickLine={false} axisLine={false} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#f6f7f9" }} />
        <ReferenceLine y={detail.medicine.daily_demand} stroke="#344054" strokeDasharray="4 4" label={{ value: "avg", fontSize: 10, fill: "#667085", position: "insideTopRight" }} />
        <Bar dataKey="dispensed" name="Units dispensed" fill="#16837a" radius={[2, 2, 0, 0]} barSize={9} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function MedicineMemories({ medicineId, generic }: { medicineId: string; generic: string }) {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const configured = health.data?.hindsight.configured ?? false;
  const { data, isLoading, error } = useQuery({
    queryKey: ["memory"], queryFn: api.memory, retry: 0, staleTime: 60000, enabled: configured,
  });
  if (health.data && !configured) {
    return <EmptyState title="Operational memory is not connected" description="Configure Hindsight in backend/.env to see this medicine's retained experience." />;
  }
  if (isLoading || !health.data) return <div className="space-y-2 p-4"><Skeleton className="h-16" /><Skeleton className="h-16" /></div>;
  if (error) return <div className="p-4 text-[12.5px] text-muted">Hindsight unavailable: {(error as Error).message}</div>;
  const key = generic.toLowerCase().split(" ")[0];
  const docs = (data?.documents ?? []).filter(
    (d) => d.medicine_id === medicineId || (d.original_text ?? "").toLowerCase().includes(key),
  );
  if (!docs.length) return <EmptyState title="No operational memory yet" description="Experiences are retained when decisions for this medicine reach an outcome." />;
  return (
    <div className="divide-y divide-line">
      {docs.map((d) => (
        <div key={d.document_id} className="px-4 py-3">
          <div className="flex items-center justify-between">
            <Badge tone="memory">{MEMORY_CATEGORY[d.category] ?? d.category_label}</Badge>
            <span className="text-[11.5px] text-muted">{fmtDate(d.occurred_on ?? d.created_at)}</span>
          </div>
          <p className="mt-1.5 text-[12.5px] leading-relaxed text-ink-2">{d.original_text}</p>
          <div className="mt-1 text-[10.5px] text-faint">Hindsight · {d.document_id} · {d.memory_unit_count} facts extracted</div>
        </div>
      ))}
    </div>
  );
}

function MedicineDrawer({ medicineId, onClose }: { medicineId: string; onClose: () => void }) {
  const refresh = useRefreshAll();
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["medicine", medicineId], queryFn: () => api.medicine(medicineId) });
  const analyze = useMutation({
    mutationFn: () => api.analyze(medicineId),
    onSuccess: (d) => {
      toast.success("Agent analysis complete", { description: `${d.headline} · ${d.memory_used.length} memories cited` });
      refresh();
    },
    onError: (e: Error) => toast.error("Analysis failed", { description: e.message }),
  });
  const m = data?.medicine;
  const active = data?.decisions.find((d) => d.status === "pending" || d.status === "approved");
  const inTransit = active?.status === "approved";

  return (
    <Drawer
      open
      onClose={onClose}
      title={m ? m.name : "Loading…"}
      subtitle={m ? `${m.id} · ${m.category} · ${m.form} · Batch ${m.batch_no} · ${m.storage}` : undefined}
      actions={
        m && (
          <Button
            variant="primary"
            loading={analyze.isPending}
            disabled={inTransit}
            title={inTransit ? "An approved order is in transit — record its outcome first" : undefined}
            onClick={() => analyze.mutate()}
          >
            {analyze.isPending ? "Agent analysing…" : active?.status === "pending" ? "Re-run agent analysis" : "Run agent analysis"}
          </Button>
        )
      }
    >
      {error && <ErrorState error={error} onRetry={() => refetch()} />}
      {isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-20" />
          <Skeleton className="h-56" />
          <Skeleton className="h-40" />
        </div>
      )}
      {data && m && (
        <div className="space-y-5">
          <Card className="grid grid-cols-2 divide-x divide-line md:grid-cols-5">
            {[
              ["Current stock", `${m.current_stock} units`, null],
              ["Daily demand", `${fmtDays(m.daily_demand)}/day`, `7-day avg ${data.demand_trend.recent_avg} (${data.demand_trend.change_pct > 0 ? "+" : ""}${data.demand_trend.change_pct}%)`],
              ["Days remaining", `${fmtDays(m.days_remaining)} days`, null],
              ["Expiry", `${m.days_to_expiry} days`, fmtDate(m.expiry_date)],
              ["Current supplier", m.primary_supplier_name, "Primary"],
            ].map(([label, value, sub], i) => (
              <div key={i} className="px-4 py-3">
                <div className="text-[11px] font-medium tracking-wide text-muted uppercase">{label}</div>
                <div className={clsx("mt-1 text-[17px] font-semibold tabular", i === 2 && (m.risk_level === "CRITICAL" ? "text-crit-700" : m.risk_level === "HIGH" ? "text-high-700" : ""), i === 3 && m.expiry_risk && "text-med-700")}>{value}</div>
                <div className="mt-0.5 text-[11.5px] text-muted">
                  {i === 2 ? <RiskBadge level={m.risk_level} /> : sub}
                </div>
              </div>
            ))}
          </Card>

          {active && <DecisionCard decision={active} />}

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader title="Stock trend" subtitle="Closing stock and deliveries, last 30 days" />
              <div className="px-2 pt-2 pb-1"><StockChart detail={data} /></div>
            </Card>
            <Card>
              <CardHeader title="Demand trend" subtitle="Units dispensed per day" />
              <div className="px-2 pt-2 pb-1"><DemandChart detail={data} /></div>
            </Card>
          </div>

          <Card>
            <CardHeader title="Supplier performance" subtitle={`Recorded deliveries of ${m.generic_name}`} />
            {data.supplier_performance.length === 0 ? (
              <EmptyState title="No delivery records yet" />
            ) : (
              <table className="w-full text-[13px]">
                <thead className="bg-canvas/70 text-left text-[11.5px] text-muted">
                  <tr>
                    <th className="px-4 py-2 font-medium">Supplier</th>
                    <th className="px-4 py-2 font-medium">Orders</th>
                    <th className="px-4 py-2 font-medium">Avg delivery</th>
                    <th className="px-4 py-2 font-medium">Contracted</th>
                    <th className="px-4 py-2 font-medium">Worst</th>
                    <th className="px-4 py-2 font-medium">On time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {data.supplier_performance.map((s) => (
                    <tr key={s.supplier_id}>
                      <td className="px-4 py-2 font-medium">{s.supplier_name}{s.supplier_id === m.primary_supplier_id && <span className="ml-1.5 text-[11px] text-muted">primary</span>}</td>
                      <td className="px-4 py-2 tabular">{s.orders}</td>
                      <td className={clsx("px-4 py-2 tabular", s.avg_delivery_days > s.expected_delivery_days + 0.5 && "font-medium text-crit-700")}>{fmtDays(s.avg_delivery_days)} days</td>
                      <td className="px-4 py-2 tabular text-muted">{fmtDays(s.expected_delivery_days)} days</td>
                      <td className="px-4 py-2 tabular">{fmtDays(s.worst_delivery_days)} days</td>
                      <td className="px-4 py-2 tabular">{s.on_time_pct}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader title="Historical incidents" />
              {data.incidents.length === 0 ? (
                <EmptyState title="No incidents recorded" />
              ) : (
                <div className="divide-y divide-line">
                  {data.incidents.map((i) => (
                    <div key={i.id} className="px-4 py-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[13px] font-medium">{i.title}</span>
                        <span className="text-[11.5px] text-muted">{fmtDate(i.occurred_at)}</span>
                      </div>
                      <div className="mt-0.5 text-[12px] text-muted">{INCIDENT_TYPE[i.type]} · {i.cause}</div>
                      <div className="mt-1 text-[12px] text-ink-2">{i.outcome}</div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
            <Card>
              <CardHeader title="Previous replenishment decisions" />
              {data.decisions.length === 0 ? (
                <EmptyState title="No decisions yet" />
              ) : (
                <div className="divide-y divide-line">
                  {data.decisions.map((d) => (
                    <div key={d.id} className="px-4 py-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[13px] font-medium">{d.final_supplier_name ?? d.recommended_supplier_name} · {d.final_quantity ?? d.recommended_quantity} units</span>
                        <DecisionStatusBadge status={d.status} />
                      </div>
                      <div className="mt-0.5 text-[12px] text-muted">{fmtDate(d.created_at)} · {d.source === "agent" ? "Agent recommendation" : "Manual decision"} · {d.urgency}</div>
                      {d.outcome && <div className="mt-1 text-[12px] text-ink-2">Outcome: {d.outcome.summary}</div>}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          <Card>
            <CardHeader
              title="Hindsight memories"
              subtitle={`Operational experience retained about ${m.generic_name}`}
            />
            <MedicineMemories medicineId={m.id} generic={m.generic_name} />
          </Card>
        </div>
      )}
    </Drawer>
  );
}
