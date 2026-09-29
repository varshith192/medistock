import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Link } from "react-router-dom";
import { useMedicineDrawer } from "../components/MedicineDrawer";
import { ActivityFeed } from "../components/ActivityFeed";
import { Badge, Card, CardHeader, EmptyState, ErrorState, PageHeader, RiskBadge, Skeleton } from "../components/ui";
import { api } from "../lib/api";
import { fmtDate, fmtDays, INCIDENT_TYPE } from "../lib/format";

function Metric({ label, value, sub, tone, to }: { label: string; value: React.ReactNode; sub?: React.ReactNode; tone?: string; to: string }) {
  return (
    <Link to={to} className="group rounded-lg border border-line bg-surface px-4 py-3.5 transition-colors hover:border-line-strong">
      <div className="text-[12px] font-medium text-muted">{label}</div>
      <div className={clsx("mt-1.5 text-[26px] leading-none font-semibold tracking-[-0.02em] tabular", tone ?? "text-ink")}>{value}</div>
      <div className="mt-2 flex items-center justify-between text-[12px] text-muted">
        <span>{sub}</span>
      </div>
    </Link>
  );
}

function ListRow({ onClick, children }: { onClick?: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left hover:bg-canvas/70">
      {children}
    </button>
  );
}

export default function Overview() {
  const drawer = useMedicineDrawer();
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["overview"], queryFn: api.overview, refetchInterval: 15000 });
  const m = data?.metrics;
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 20000 });

  if (error && !data) {
    return (
      <>
        <PageHeader title="Inventory Operations" subtitle="Monitor risk, review agent decisions, and learn from operational history." />
        <ErrorState error={error} onRetry={() => refetch()} />
      </>
    );
  }

  return (
    <>
      <PageHeader title="Inventory Operations" subtitle="Monitor risk, review agent decisions, and learn from operational history." />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {isLoading || !m ? (
          Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-[98px]" />)
        ) : (
          <>
            <Metric label="Total Medicines" value={m.total_medicines} sub="Active SKUs" to="/inventory" />
            <Metric label="Critical Stock Risks" value={m.stock_risks} sub={`${m.critical} critical · ${m.high} high`} tone="text-crit-700" to="/inventory" />
            <Metric label="Expiry Risks" value={m.expiry_risks} sub={`Within ${m.expiry_threshold_days} days`} tone="text-med-700" to="/inventory" />
            <Metric label="Pending Decisions" value={m.pending_decisions} sub={`${m.awaiting_outcome} awaiting outcome`} tone={m.pending_decisions ? "text-high-700" : undefined} to="/agent" />
            <Metric label="Supplier Issues" value={m.supplier_issues} sub="Below 75% on-time" to="/suppliers" />
            <Metric
              label="Successful Decisions"
              value={m.success_rate === null ? "—" : `${m.success_rate}%`}
              sub={`${m.decisions_completed} with recorded outcome`}
              tone="text-ok-700"
              to="/decisions"
            />
          </>
        )}
      </div>

      {m && health.data && !health.data.hindsight.connected && (
        <Link
          to="/settings"
          className="mt-3 flex items-center gap-3 rounded-lg border border-med-200 bg-med-50 px-4 py-2.5 text-[13px] text-med-700 hover:bg-med-50/70"
        >
          <span>
            Operational memory (Hindsight) is not connected — the agent is deciding from current data only.{" "}
            {health.data.hindsight.error}
          </span>
        </Link>
      )}
      {m && health.data?.hindsight.connected && (
        <Link
          to="/memory"
          className="mt-3 flex items-center gap-3 rounded-lg border border-memory-200 bg-memory-50/60 px-4 py-2.5 text-[13px] text-memory-700 hover:bg-memory-50"
        >
          <span>
            <b className="tabular">{m.experiences_retained}</b> operational experiences in Hindsight memory ·{" "}
            <b className="tabular">{m.memory_influenced_decisions_7d}</b> agent decisions influenced by memory in the last 7 days
          </span>
        </Link>
      )}

      <h2 className="mt-7 mb-3 text-[12px] font-semibold tracking-wider text-muted uppercase">Risk Overview</h2>
      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader title="Critical stock-out risks" subtitle="Lowest days of cover" action={<Link to="/inventory" className="text-[12px] font-medium text-brand-700">View all</Link>} />
          {!data ? <Skeleton className="m-4 h-40" /> : data.stock_risks.length === 0 ? <EmptyState title="No stock-out risks" /> : (
            <div className="divide-y divide-line">
              {data.stock_risks.map((i) => (
                <ListRow key={i.id} onClick={() => drawer.open(i.id)}>
                  <div className="min-w-0">
                    <div className="truncate text-[13px] font-medium">{i.name}</div>
                    <div className="text-[12px] text-muted tabular">{i.current_stock} units · {fmtDays(i.daily_demand)}/day</div>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <RiskBadge level={i.risk_level} />
                    <span className="text-[12px] font-medium tabular">{fmtDays(i.days_remaining)} days</span>
                  </div>
                </ListRow>
              ))}
            </div>
          )}
        </Card>
        <Card>
          <CardHeader title="Upcoming expiries" subtitle={m ? `Within ${m.expiry_threshold_days} days` : undefined} />
          {!data ? <Skeleton className="m-4 h-40" /> : data.expiry_risks.length === 0 ? <EmptyState title="No expiry risks" /> : (
            <div className="divide-y divide-line">
              {data.expiry_risks.map((i) => (
                <ListRow key={i.id} onClick={() => drawer.open(i.id)}>
                  <div className="min-w-0">
                    <div className="truncate text-[13px] font-medium">{i.name}</div>
                    <div className="text-[12px] text-muted">
                      {i.units_at_expiry_risk > 0 ? `${i.units_at_expiry_risk} units likely to expire` : "Expected to sell through"}
                    </div>
                  </div>
                  <div className="shrink-0 text-right">
                    <div className={clsx("text-[13px] font-semibold tabular", i.days_to_expiry <= 30 ? "text-crit-700" : "text-med-700")}>{i.days_to_expiry} days</div>
                    <div className="text-[11.5px] text-muted">{fmtDate(i.expiry_date)}</div>
                  </div>
                </ListRow>
              ))}
            </div>
          )}
        </Card>
        <Card>
          <CardHeader title="Supplier delays" subtitle="Reliability issues and open orders" action={<Link to="/suppliers" className="text-[12px] font-medium text-brand-700">Suppliers</Link>} />
          {!data ? <Skeleton className="m-4 h-40" /> : (
            <div className="divide-y divide-line">
              {data.supplier_issues.map((s) => (
                <div key={s.id} className="flex items-center justify-between px-4 py-2.5">
                  <div>
                    <div className="text-[13px] font-medium">{s.name}</div>
                    <div className="text-[12px] text-muted">{s.legal_name}</div>
                  </div>
                  <div className="shrink-0 text-right whitespace-nowrap">
                    <div className="text-[13px] font-semibold text-crit-700 tabular">{fmtDays(s.avg_delivery_days)}d <span className="font-normal text-muted">vs {fmtDays(s.expected_delivery_days)}d</span></div>
                    <div className="text-[11.5px] text-muted tabular">{s.on_time_pct}% on time</div>
                  </div>
                </div>
              ))}
              {data.overdue_orders.map((o) => (
                <div key={o.id} className="flex items-center justify-between px-4 py-2.5">
                  <div>
                    <div className="text-[13px] font-medium">{o.medicine_name}</div>
                    <div className="text-[12px] text-muted">{o.id} · {o.supplier_name}</div>
                  </div>
                  <Badge tone="high">Overdue {fmtDays(o.elapsed_days - o.expected_days)}d</Badge>
                </div>
              ))}
              {data.supplier_issues.length + data.overdue_orders.length === 0 && <EmptyState title="No supplier issues" />}
            </div>
          )}
        </Card>
        <Card>
          <CardHeader title="Unresolved incidents" action={<Link to="/incidents" className="text-[12px] font-medium text-brand-700">Incidents</Link>} />
          {!data ? <Skeleton className="m-4 h-40" /> : data.open_incidents.length === 0 ? <EmptyState title="No open incidents" /> : (
            <div className="divide-y divide-line">
              {data.open_incidents.map((i) => (
                <ListRow key={i.id} onClick={() => drawer.open(i.medicine_id)}>
                  <div className="min-w-0">
                    <div className="truncate text-[13px] font-medium">{i.title}</div>
                    <div className="truncate text-[12px] text-muted">{INCIDENT_TYPE[i.type]} · {fmtDate(i.occurred_at)}</div>
                  </div>
                  <Badge tone={i.severity === "critical" ? "crit" : i.severity === "high" ? "high" : i.severity === "medium" ? "med" : "neutral"}>
                    {i.severity}
                  </Badge>
                </ListRow>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="mt-7 grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Card>
          <CardHeader title="Agent Activity" subtitle="Detections, Hindsight recall and retain operations, recommendations and outcomes" action={<Link to="/agent" className="text-[12px] font-medium text-brand-700">Decision center</Link>} />
          <ActivityFeed limit={14} />
        </Card>
        <Card>
          <CardHeader title="Inventory risk distribution" subtitle="By days of cover" />
          {!data ? <Skeleton className="m-4 h-40" /> : (
            <div className="space-y-3 px-4 py-4">
              {(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const).map((lvl) => {
                const n = data.risk_distribution[lvl];
                const pct = m!.total_medicines ? (100 * n) / m!.total_medicines : 0;
                return (
                  <div key={lvl}>
                    <div className="mb-1 flex items-center justify-between text-[12.5px]">
                      <span className="flex items-center gap-2"><RiskBadge level={lvl} /><span className="text-muted">{{ CRITICAL: "≤ 2 days", HIGH: "2–4 days", MEDIUM: "4–7 days", LOW: "> 7 days" }[lvl]}</span></span>
                      <span className="font-semibold tabular">{n}</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-canvas">
                      <div className={clsx("h-full rounded-full", { CRITICAL: "bg-crit-600", HIGH: "bg-high-600", MEDIUM: "bg-med-600", LOW: "bg-ok-600" }[lvl])} style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
              <p className="pt-1 text-[12px] text-muted">
                Risk tiers are computed deterministically from current stock ÷ average daily demand.
              </p>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
