import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { ChevronRight } from "lucide-react";
import { Fragment, useState } from "react";
import { Badge, Card, ErrorState, PageHeader, SkeletonRows } from "../components/ui";
import { api } from "../lib/api";
import { fmtDate, fmtDays } from "../lib/format";
import type { Supplier } from "../lib/types";

const RELIABILITY_TONE = { Reliable: "ok", Watch: "med", "Needs Attention": "crit", "No history": "neutral" } as const;
const DELAY_TONE = { High: "crit", Medium: "med", Low: "ok" } as const;

function SupplierDetail({ s }: { s: Supplier }) {
  return (
    <div className="grid gap-4 bg-canvas/60 px-6 py-4 lg:grid-cols-2">
      <div>
        <div className="mb-2 text-[12px] font-semibold text-ink">Delivery performance by medicine</div>
        <table className="w-full text-[12.5px]">
          <thead className="text-left text-[11px] text-muted">
            <tr><th className="py-1 font-medium">Medicine</th><th className="py-1 font-medium">Orders</th><th className="py-1 font-medium">Avg</th><th className="py-1 font-medium">Worst</th><th className="py-1 font-medium">On time</th></tr>
          </thead>
          <tbody className="divide-y divide-line">
            {s.by_medicine.map((m) => (
              <tr key={m.medicine}>
                <td className="py-1.5 font-medium">{m.medicine}</td>
                <td className="py-1.5 tabular">{m.orders}</td>
                <td className={clsx("py-1.5 tabular", m.avg_days > m.expected_days + 0.5 && "font-semibold text-crit-700")}>{fmtDays(m.avg_days)}d <span className="font-normal text-muted">/ {fmtDays(m.expected_days)}d</span></td>
                <td className="py-1.5 tabular">{fmtDays(m.worst_days)}d</td>
                <td className="py-1.5 tabular">{m.on_time_pct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div>
        <div className="mb-2 text-[12px] font-semibold text-ink">Recent orders</div>
        <table className="w-full text-[12.5px]">
          <thead className="text-left text-[11px] text-muted">
            <tr><th className="py-1 font-medium">Order</th><th className="py-1 font-medium">Medicine</th><th className="py-1 font-medium">Qty</th><th className="py-1 font-medium">Delivery</th><th className="py-1 font-medium">Status</th></tr>
          </thead>
          <tbody className="divide-y divide-line">
            {s.recent_orders.map((o) => (
              <tr key={o.id}>
                <td className="py-1.5"><div className="font-mono text-[11.5px]">{o.id}</div><div className="text-[11px] text-muted">{fmtDate(o.ordered_at)}</div></td>
                <td className="py-1.5">{o.medicine_name}</td>
                <td className="py-1.5 tabular">{o.quantity}</td>
                <td className="py-1.5 tabular">{o.actual_days !== null ? `${fmtDays(o.actual_days)}d` : "—"} <span className="text-muted">/ {fmtDays(o.expected_days)}d</span></td>
                <td className="py-1.5">
                  <Badge tone={o.status === "delivered" ? "ok" : o.status === "delivered_late" ? "med" : o.status === "in_transit" ? "brand" : "neutral"}>
                    {{ delivered: "On time", delivered_late: "Late", in_transit: "In transit", cancelled: "Cancelled" }[o.status]}
                  </Badge>
                  {o.urgency !== "routine" && <span className="ml-1 text-[11px] text-muted capitalize">{o.urgency}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function Suppliers() {
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["suppliers"], queryFn: api.suppliers });
  const [open, setOpen] = useState<string | null>("SUP-A");
  return (
    <>
      <PageHeader title="Supplier Intelligence" subtitle="Contracted versus actual delivery performance, computed from every recorded order." />
      {error && !data ? <ErrorState error={error} onRetry={() => refetch()} /> : (
      <Card className="overflow-hidden">
        {isLoading ? <SkeletonRows rows={6} /> : (
          <table className="w-full text-[13px]">
            <thead className="border-b border-line bg-canvas/80 text-left text-[11.5px] text-muted">
              <tr>
                <th className="w-8" />
                <th className="px-3 py-2.5 font-medium">Supplier</th>
                <th className="px-3 py-2.5 font-medium">Medicines</th>
                <th className="px-3 py-2.5 font-medium">Average Delivery</th>
                <th className="px-3 py-2.5 font-medium">Expected Delivery</th>
                <th className="px-3 py-2.5 font-medium">Delay Rate</th>
                <th className="px-3 py-2.5 font-medium">Successful Orders</th>
                <th className="px-3 py-2.5 pr-4 font-medium">Reliability</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data?.map((s) => (
                <Fragment key={s.id}>
                  <tr className="cursor-pointer hover:bg-canvas/70" onClick={() => setOpen(open === s.id ? null : s.id)}>
                    <td className="pl-3"><ChevronRight className={clsx("size-4 text-faint transition-transform", open === s.id && "rotate-90")} /></td>
                    <td className="px-3 py-3">
                      <div className="font-semibold">{s.name}</div>
                      <div className="text-[12px] text-muted">{s.legal_name} · {s.city} · MOQ {s.min_order_qty}</div>
                    </td>
                    <td className="px-3">
                      <div className="text-ink-2">{s.primary_for.slice(0, 2).join(", ")}{s.primary_for.length > 2 ? ` +${s.primary_for.length - 2}` : ""}</div>
                      <div className="text-[11.5px] text-muted">Primary for {s.primary_for.length} · approved for {s.approved_for_count}</div>
                    </td>
                    <td className={clsx("px-3 font-semibold tabular", s.avg_delivery_days !== null && s.avg_delivery_days > s.expected_delivery_days * 1.25 ? "text-crit-700" : "text-ink")}>
                      {s.avg_delivery_days === null ? "—" : `${fmtDays(s.avg_delivery_days)} days`}
                    </td>
                    <td className="px-3 tabular text-ink-2">{fmtDays(s.contracted_lead_days)} days</td>
                    <td className="px-3"><Badge tone={DELAY_TONE[s.delay_rate_label]}>{s.delay_rate_label} · {s.delay_rate_pct}%</Badge></td>
                    <td className="px-3 tabular"><span className="font-medium">{s.on_time_pct}%</span> <span className="text-[12px] text-muted">of {s.orders}</span></td>
                    <td className="px-3 pr-4"><Badge tone={RELIABILITY_TONE[s.reliability]} dot>{s.reliability}</Badge></td>
                  </tr>
                  {open === s.id && (
                    <tr><td colSpan={8} className="p-0"><SupplierDetail s={s} /></td></tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      )}
      <p className="mt-3 text-[12px] text-muted">
        Successful orders = delivered within half a day of the contracted lead time. The agent learns medicine-specific supplier behaviour
        from outcomes retained in Hindsight — for example, Supplier A's delays are concentrated on antibiotics.
      </p>
    </>
  );
}
