import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { Health } from "../lib/types";
import { Button } from "./ui";
import ErrorBoundary from "./ErrorBoundary";
import { MedicineDrawerProvider } from "./MedicineDrawer";

const NAV = [
  { to: "/", label: "Overview", end: true },
  { to: "/inventory", label: "Inventory" },
  { to: "/agent", label: "Agent Decisions", badge: "pending" as const },
  { to: "/memory", label: "Memory" },
  { to: "/suppliers", label: "Suppliers" },
  { to: "/incidents", label: "Incidents" },
  { to: "/decisions", label: "Decisions" },
  { to: "/settings", label: "Settings" },
];

function StatusRow({ state, label, title }: { state: "ok" | "warn" | "down" | "loading"; label: string; title?: string }) {
  return (
    <div className="flex items-center gap-2 text-[12.5px] text-ink-2" title={title}>
      <span
        className={clsx(
          "size-2 rounded-full",
          state === "ok" && "bg-ok-600",
          state === "warn" && "bg-med-600",
          state === "down" && "bg-crit-600",
          state === "loading" && "animate-pulse-dot bg-faint",
        )}
      />
      {label}
    </div>
  );
}

function SystemStatus() {
  const { data, isLoading, isError } = useQuery<Health>({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 20000,
  });
  if (isLoading) {
    return (
      <>
        <StatusRow state="loading" label="Agent" />
        <StatusRow state="loading" label="Hindsight" />
        <StatusRow state="loading" label="Database" />
      </>
    );
  }
  if (isError || !data) {
    return <StatusRow state="down" label="Backend unreachable" title="Start the FastAPI backend on port 8000" />;
  }
  const agentState = !data.agent.configured ? "warn" : data.agent.ok === false ? "warn" : "ok";
  const agentLabel = !data.agent.configured
    ? "Agent · rules mode"
    : data.agent.ok === false
      ? "Agent · LLM degraded"
      : "Agent Online";
  const seed = data.hindsight.seed;
  const hsLabel = !data.hindsight.configured
    ? "Hindsight not configured"
    : !data.hindsight.connected
      ? "Hindsight disconnected"
      : seed.state === "running"
        ? `Hindsight · loading ${seed.done}/${seed.total}`
        : "Hindsight Connected";
  return (
    <>
      <StatusRow state={agentState} label={agentLabel} title={data.agent.error ?? `${data.agent.provider} · ${data.agent.model}`} />
      <StatusRow
        state={data.hindsight.connected ? (seed.state === "running" ? "warn" : "ok") : "down"}
        label={hsLabel}
        title={data.hindsight.error ?? `Bank ${data.hindsight.bank_id}${data.hindsight.latency_ms ? ` · ${data.hindsight.latency_ms} ms` : ""}`}
      />
      <StatusRow state={data.database.ok ? "ok" : "down"} label={data.database.ok ? "Database Connected" : "Database error"} />
    </>
  );
}

function PendingCount() {
  const { data } = useQuery({ queryKey: ["overview"], queryFn: api.overview, refetchInterval: 15000 });
  const n = data?.metrics.pending_decisions ?? 0;
  if (!n) return null;
  return (
    <span className="ml-auto rounded-full bg-high-50 px-1.5 text-[11px] font-semibold text-high-700 ring-1 ring-high-200 tabular">
      {n}
    </span>
  );
}

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const today = new Date().toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
  return (
    <MedicineDrawerProvider>
      <div className="flex h-full">
        <aside className="flex w-[232px] shrink-0 flex-col border-r border-line bg-surface">
          <div className="flex items-center gap-2.5 px-4 pt-5 pb-6">
            <div className="grid size-8 place-items-center rounded-lg bg-brand-700">
              <svg viewBox="0 0 32 32" className="size-4.5" aria-hidden>
                <path d="M13 6h6v7h7v6h-7v7h-6v-7H6v-6h7z" fill="#fff" />
              </svg>
            </div>
            <div>
              <div className="text-[14.5px] leading-tight font-semibold tracking-[-0.01em] text-ink">MediStock 360</div>
              <div className="text-[11.5px] leading-tight text-muted">Inventory operations</div>
            </div>
          </div>
          <nav className="flex-1 space-y-0.5 px-2.5">
            {NAV.map(({ to, label, end, badge }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  clsx(
                    "flex h-9 items-center rounded-md border-l-2 px-3 text-[13.5px] font-medium transition-colors",
                    isActive ? "border-brand-600 bg-brand-50 text-brand-700" : "border-transparent text-ink-2 hover:bg-canvas",
                  )
                }
              >
                {label}
                {badge === "pending" && <PendingCount />}
              </NavLink>
            ))}
          </nav>
          <div className="m-3 rounded-lg border border-line bg-canvas/70 px-3 py-3">
            <div className="mb-2 text-[11px] font-semibold tracking-wider text-muted uppercase">System Status</div>
            <div className="space-y-1.5">
              <SystemStatus />
            </div>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-14 shrink-0 items-center justify-between border-b border-line bg-surface px-7">
            <div className="flex items-center gap-2 text-[13px]">
              <span className="font-medium text-ink">Central Pharmacy · Main Store</span>
              <span className="text-faint">/</span>
              <span className="text-muted">{today}</span>
            </div>
            <div className="flex items-center gap-3">
              <Button size="sm" variant="secondary" onClick={() => navigate("/demo")}>
                Memory demo
              </Button>
              <div className="flex items-center gap-2 border-l border-line pl-3">
                <div className="grid size-7 place-items-center rounded-full bg-brand-100 text-[11px] font-semibold text-brand-700">OM</div>
                <div className="text-[12.5px] leading-tight">
                  <div className="font-medium text-ink">Operations Manager</div>
                  <div className="text-muted">Inventory</div>
                </div>
              </div>
            </div>
          </header>
          <main className="thin-scroll flex-1 overflow-y-auto">
            <div className="mx-auto max-w-[1400px] px-7 py-6">
              <ErrorBoundary key={location.pathname}>
                <Outlet />
              </ErrorBoundary>
            </div>
          </main>
        </div>
      </div>
    </MedicineDrawerProvider>
  );
}
