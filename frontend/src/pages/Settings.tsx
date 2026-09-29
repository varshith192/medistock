import { useMutation, useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge, Button, Card, CardHeader, ErrorState, Field, inputClass, Modal, PageHeader, RiskBadge, Skeleton } from "../components/ui";
import { api } from "../lib/api";
import { useRefreshAll, useRefreshMemory } from "../lib/hooks";
import type { RiskLevel } from "../lib/types";

function Status({ ok, children }: { ok: boolean | null | undefined; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[12.5px]">
      <span className={clsx("size-2 rounded-full", ok ? "bg-ok-600" : ok === false ? "bg-crit-600" : "bg-med-600")} />
      {children}
    </span>
  );
}

export default function SettingsPage() {
  const refresh = useRefreshAll();
  const refreshMemory = useRefreshMemory();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 5000 });
  const [expiry, setExpiry] = useState(60);
  const [cover, setCover] = useState(7);
  const [confirmReset, setConfirmReset] = useState(false);
  useEffect(() => {
    if (settings.data) {
      setExpiry(settings.data.expiry_threshold_days);
      setCover(settings.data.target_cover_days);
    }
  }, [settings.data]);

  const save = useMutation({
    mutationFn: () => api.saveSettings({ expiry_threshold_days: expiry, target_cover_days: cover }),
    onSuccess: () => { toast.success("Settings saved"); settings.refetch(); refresh(); },
    onError: (e: Error) => toast.error("Could not save settings", { description: e.message }),
  });
  const seed = useMutation({
    mutationFn: api.seedMemory,
    onSuccess: () => { toast.success("Historical experience is in Hindsight"); refreshMemory(); refresh(); },
    onError: (e: Error) => toast.error("Could not load history", { description: e.message }),
  });
  const reset = useMutation({
    mutationFn: api.demoReset,
    onSuccess: (r) => {
      toast.success("Demo data reset", { description: `Operational data restored; ${r.removed_memories} demo memories removed from Hindsight.` });
      setConfirmReset(false);
      refresh();
      refreshMemory();
    },
    onError: (e: Error) => toast.error("Reset failed", { description: e.message }),
  });

  const cycle = useMutation({
    mutationFn: () => api.demoRun("new_situation"),
    onSuccess: (s) => {
      toast.success("New demand cycle simulated", {
        description: `${s.medicine.name}: ${s.medicine.current_stock} units at ${s.medicine.daily_demand}/day (${s.medicine.days_remaining} days).`,
      });
      refresh();
    },
    onError: (e: Error) => toast.error("Simulation failed", { description: e.message }),
  });
  const h = health.data;
  return (
    <>
      <PageHeader title="Settings" subtitle="Risk policy, integrations and demo data." />
      {settings.error && <ErrorState error={settings.error} onRetry={() => settings.refetch()} />}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Risk policy" subtitle="Deterministic rules applied by the risk engine before any AI reasoning" />
          {!settings.data ? <Skeleton className="m-4 h-40" /> : (
            <div className="space-y-4 px-4 py-4">
              <div className="grid grid-cols-4 gap-2">
                {(Object.entries(settings.data.risk_rules) as [RiskLevel, string][]).map(([lvl, rule]) => (
                  <div key={lvl} className="rounded-md border border-line px-2.5 py-2">
                    <RiskBadge level={lvl} />
                    <div className="mt-1.5 text-[12.5px] text-ink-2 tabular">{rule} of cover</div>
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Expiry risk threshold (days)" hint="Batches expiring within this window are flagged">
                  <input type="number" min={7} max={365} className={inputClass} value={expiry} onChange={(e) => setExpiry(Number(e.target.value))} />
                </Field>
                <Field label="Target cover after delivery (days)" hint="Used to size recommended order quantities">
                  <input type="number" min={3} max={30} step={0.5} className={inputClass} value={cover} onChange={(e) => setCover(Number(e.target.value))} />
                </Field>
              </div>
              <div className="flex justify-end">
                <Button variant="primary" loading={save.isPending} onClick={() => save.mutate()}>Save policy</Button>
              </div>
            </div>
          )}
        </Card>

        <Card>
          <CardHeader title="Integrations" subtitle="Credentials are read from backend/.env and never sent to the browser" />
          {!h ? <Skeleton className="m-4 h-40" /> : (
            <div className="divide-y divide-line">
              <div className="flex items-start gap-3 px-4 py-3.5">
                <div className="flex-1">
                  <div className="text-[13px] font-medium">Decision agent LLM</div>
                  <div className="text-[12px] text-muted">{h.agent.provider} · {h.agent.model}</div>
                  {h.agent.error && <div className="mt-1 text-[12px] text-crit-700">{h.agent.error}</div>}
                  {!h.agent.configured && <div className="mt-1 text-[12px] text-muted">Without a key the agent uses its deterministic decision engine (still memory-aware).</div>}
                </div>
                <Status ok={h.agent.configured ? h.agent.ok ?? true : null}>{h.agent.configured ? (h.agent.ok === false ? "Degraded" : "Configured") : "Rules mode"}</Status>
              </div>
              <div className="flex items-start gap-3 px-4 py-3.5">
                <div className="flex-1">
                  <div className="text-[13px] font-medium">Hindsight operational memory</div>
                  <div className="font-mono text-[11.5px] text-muted">{h.hindsight.base_url} · bank {h.hindsight.bank_id}</div>
                  {h.hindsight.error && <div className="mt-1 text-[12px] text-crit-700">{h.hindsight.error}</div>}
                  <div className="mt-2 flex items-center gap-2">
                    <Badge tone={h.hindsight.seed.state === "done" ? "ok" : h.hindsight.seed.state === "error" ? "crit" : "neutral"}>
                      Historical experience: {h.hindsight.seed.state === "running" ? `loading ${h.hindsight.seed.done}/${h.hindsight.seed.total}` : h.hindsight.seed.state}
                    </Badge>
                    <Button size="sm" disabled={!h.hindsight.connected} loading={seed.isPending || h.hindsight.seed.state === "running"} onClick={() => seed.mutate()}>
                      Sync history
                    </Button>
                  </div>
                </div>
                <Status ok={h.hindsight.connected}>{h.hindsight.connected ? "Connected" : "Disconnected"}</Status>
              </div>
              <div className="flex items-start gap-3 px-4 py-3.5">
                <div className="flex-1">
                  <div className="text-[13px] font-medium">Operational database</div>
                  <div className="text-[12px] text-muted">SQLite · {h.database.medicines ?? 0} medicines</div>
                </div>
                <Status ok={h.database.ok}>{h.database.ok ? "Connected" : "Error"}</Status>
              </div>
            </div>
          )}
        </Card>

        <Card>
          <CardHeader title="Demo data" subtitle="Restore the seeded dataset for a fresh demonstration" />
          <div className="flex items-center justify-between gap-4 px-4 py-4">
            <p className="text-[12.5px] text-ink-2">
              Restores inventory, orders, incidents and decisions to the original synthetic dataset and removes experiences the agent
              retained during demos. Historical experience in Hindsight is kept.
            </p>
            <Button variant="danger" onClick={() => setConfirmReset(true)}>Reset demo data</Button>
          </div>
          <div className="flex items-center justify-between gap-4 border-t border-line px-4 py-4">
            <p className="text-[12.5px] text-ink-2">
              Simulate the next demand cycle for Amoxicillin 500mg: stock is consumed back down to about 2.6 days of cover so the
              agent faces a similar situation again.
            </p>
            <Button loading={cycle.isPending} onClick={() => cycle.mutate()}>Simulate demand cycle</Button>
          </div>
        </Card>

        <Card>
          <CardHeader title="Data safety" />
          <div className="flex gap-3 px-4 py-4 text-[12.5px] text-ink-2">
            <p>
              MediStock 360 stores operational inventory data only — stock, demand, suppliers, orders and decisions. It holds no patient
              names, prescriptions or medical records, and it does not provide clinical or prescribing advice. All data in this prototype is synthetic.
            </p>
          </div>
        </Card>
      </div>

      <Modal
        open={confirmReset}
        onClose={() => setConfirmReset(false)}
        title="Reset demo data?"
        subtitle="This cannot be undone."
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmReset(false)}>Cancel</Button>
            <Button variant="danger" loading={reset.isPending} onClick={() => reset.mutate()}>Reset demo data</Button>
          </>
        }
      >
        <p className="text-[13px] text-ink-2">
          All decisions, approvals and outcomes recorded since the last reset will be removed, and the experiences the agent retained
          from them will be deleted from the Hindsight bank.
        </p>
      </Modal>
    </>
  );
}
