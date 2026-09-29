import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { ArrowDown, ArrowUp, ChevronsUpDown, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { useMedicineDrawer } from "../components/MedicineDrawer";
import { Badge, Card, EmptyState, ErrorState, inputBase, inputClass, PageHeader, RiskBadge, SegmentedControl, SkeletonRows } from "../components/ui";
import { api } from "../lib/api";
import { fmtDays } from "../lib/format";
import type { Medicine, RiskLevel } from "../lib/types";

type SortKey = "name" | "category" | "current_stock" | "daily_demand" | "days_remaining" | "days_to_expiry" | "primary_supplier_name" | "risk";
const RISK_RANK: Record<RiskLevel, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

const STATUS_TONE = {
  "Action Required": "crit",
  "Decision Pending": "high",
  "Awaiting Delivery": "brand",
  Monitor: "med",
  Healthy: "ok",
} as const;

export default function Inventory() {
  const drawer = useMedicineDrawer();
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["inventory"], queryFn: api.inventory, refetchInterval: 20000 });
  const [q, setQ] = useState("");
  const [risk, setRisk] = useState<"ALL" | RiskLevel>("ALL");
  const [category, setCategory] = useState("ALL");
  const [flag, setFlag] = useState<"ALL" | "EXPIRY" | "ACTION">("ALL");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "days_remaining", dir: 1 });

  const categories = useMemo(() => Array.from(new Set((data ?? []).map((m) => m.category))).sort(), [data]);
  const counts = useMemo(() => {
    const c = { ALL: data?.length ?? 0, CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 } as Record<string, number>;
    data?.forEach((m) => c[m.risk_level]++);
    return c;
  }, [data]);

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const filtered = (data ?? []).filter(
      (m) =>
        (risk === "ALL" || m.risk_level === risk) &&
        (category === "ALL" || m.category === category) &&
        (flag === "ALL" || (flag === "EXPIRY" ? m.expiry_risk : ["Action Required", "Decision Pending"].includes(m.agent_status))) &&
        (!needle || `${m.name} ${m.generic_name} ${m.id} ${m.primary_supplier_name}`.toLowerCase().includes(needle)),
    );
    const val = (m: Medicine): string | number =>
      sort.key === "risk" ? RISK_RANK[m.risk_level] : ((m[sort.key as keyof Medicine] as string | number) ?? "");
    return filtered.sort((a, b) => {
      const va = val(a), vb = val(b);
      return (typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb))) * sort.dir;
    });
  }, [data, q, risk, category, flag, sort]);

  const Th = ({ k, children, className }: { k: SortKey; children: React.ReactNode; className?: string }) => (
    <th className={clsx("px-3 py-2.5 font-medium", className)}>
      <button
        className="inline-flex items-center gap-1 hover:text-ink"
        onClick={() => setSort((s) => ({ key: k, dir: s.key === k ? (s.dir === 1 ? -1 : 1) : 1 }))}
      >
        {children}
        {sort.key === k ? (sort.dir === 1 ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />) : <ChevronsUpDown className="size-3 text-faint" />}
      </button>
    </th>
  );

  return (
    <>
      <PageHeader title="Inventory" subtitle="Current stock position, days of cover and agent status for every medicine." />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative w-72">
          <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-faint" />
          <input className={clsx(inputClass, "pl-8")} placeholder="Search medicine, generic, supplier…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <SegmentedControl
          value={risk}
          onChange={setRisk}
          options={(["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"] as const).map((r) => ({ value: r, label: r === "ALL" ? "All" : r.charAt(0) + r.slice(1).toLowerCase(), count: counts[r] }))}
        />
        <select className={clsx(inputBase, "w-48")} value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Category">
          <option value="ALL">All categories</option>
          {categories.map((c) => <option key={c}>{c}</option>)}
        </select>
        <select className={clsx(inputBase, "w-44")} value={flag} onChange={(e) => setFlag(e.target.value as typeof flag)} aria-label="Flag">
          <option value="ALL">All statuses</option>
          <option value="ACTION">Needs a decision</option>
          <option value="EXPIRY">Expiry risk</option>
        </select>
        <span className="ml-auto text-[12.5px] text-muted tabular">{rows.length} of {data?.length ?? 0} medicines</span>
      </div>

      {error && !data ? <ErrorState error={error} onRetry={() => refetch()} /> : (
      <Card className="overflow-hidden">
        {isLoading ? (
          <SkeletonRows rows={10} />
        ) : rows.length === 0 ? (
          <EmptyState title="No medicines match these filters" description="Clear the search or choose a different risk level." />
        ) : (
          <div className="thin-scroll overflow-x-auto">
            <table className="w-full min-w-[1080px] text-[13px]">
              <thead className="sticky top-0 border-b border-line bg-canvas/80 text-left text-[11.5px] text-muted">
                <tr>
                  <Th k="name" className="pl-4">Medicine</Th>
                  <Th k="category">Category</Th>
                  <Th k="current_stock" className="text-right">Current Stock</Th>
                  <Th k="daily_demand">Daily Demand</Th>
                  <Th k="days_remaining">Days Remaining</Th>
                  <Th k="days_to_expiry">Expiry</Th>
                  <Th k="primary_supplier_name">Primary Supplier</Th>
                  <Th k="risk">Risk</Th>
                  <th className="px-3 py-2.5 pr-4 font-medium">Agent Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((m) => (
                  <tr
                    key={m.id}
                    tabIndex={0}
                    onClick={() => drawer.open(m.id)}
                    onKeyDown={(e) => e.key === "Enter" && drawer.open(m.id)}
                    className="cursor-pointer hover:bg-canvas/70 focus:bg-canvas/70 focus:outline-none"
                  >
                    <td className="py-2.5 pr-3 pl-4">
                      <div className="font-medium text-ink">{m.name}</div>
                      <div className="text-[11.5px] text-muted">{m.id} · {m.form}{m.storage.startsWith("Cold") ? " · Cold chain" : ""}</div>
                    </td>
                    <td className="px-3 text-ink-2">{m.category}</td>
                    <td className="px-3 text-right font-medium tabular">{m.current_stock}</td>
                    <td className="px-3 tabular text-ink-2">{fmtDays(m.daily_demand)}/day</td>
                    <td className={clsx("px-3 font-semibold tabular", m.risk_level === "CRITICAL" ? "text-crit-700" : m.risk_level === "HIGH" ? "text-high-700" : "text-ink")}>
                      {fmtDays(m.days_remaining)} days
                    </td>
                    <td className="px-3">
                      <span className={clsx("tabular", m.expiry_risk ? "font-medium text-med-700" : "text-ink-2")}>{m.days_to_expiry} days</span>
                      {m.expiry_risk && m.units_at_expiry_risk > 0 && <div className="text-[11px] text-med-700">{m.units_at_expiry_risk} units at risk</div>}
                    </td>
                    <td className="px-3 text-ink-2">
                      {m.primary_supplier_name}
                      {m.supplier_risk && <span className="ml-1.5 text-[11px] text-crit-700">delays</span>}
                    </td>
                    <td className="px-3"><RiskBadge level={m.risk_level} /></td>
                    <td className="px-3 pr-4"><Badge tone={STATUS_TONE[m.agent_status]}>{m.agent_status}</Badge></td>
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
