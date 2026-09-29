import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Loader2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";
import DecisionCard from "../components/decision/DecisionCard";
import { Badge, Button, Card, PageHeader, RiskBadge } from "../components/ui";
import { api } from "../lib/api";
import { fmtDate, fmtDays } from "../lib/format";
import { useRefreshAll, useRefreshMemory } from "../lib/hooks";
import type { Decision, MemoryDocument, RecalledMemory } from "../lib/types";

type StepKey = "history" | "recall" | "risk" | "recommend" | "approve" | "outcome" | "retain" | "new" | "updated";

const STEPS: { id: StepKey; title: string; caption: string }[] = [
  { id: "history", title: "Previous Supplier A delay", caption: "A past incident already exists in Hindsight" },
  { id: "recall", title: "Hindsight recall", caption: "The agent recalls relevant operational experience" },
  { id: "risk", title: "Current Amoxicillin risk", caption: "Deterministic risk from today's stock and demand" },
  { id: "recommend", title: "Agent recommendation", caption: "Same agent, with and without memory" },
  { id: "approve", title: "Manager approval", caption: "The manager approves and a purchase order is raised" },
  { id: "outcome", title: "Successful outcome", caption: "Delivery result is recorded" },
  { id: "retain", title: "Hindsight retain", caption: "The experience becomes operational memory" },
  { id: "new", title: "New similar situation", caption: "Next demand cycle: Amoxicillin runs low again" },
  { id: "updated", title: "Updated recommendation", caption: "The agent now uses the accumulated experience" },
];

function StepShell({
  index, title, caption, state, children, action,
}: {
  index: number; title: string; caption: string; state: "done" | "active" | "todo"; children?: ReactNode; action?: ReactNode;
}) {
  return (
    <div className="grid grid-cols-[36px_1fr] gap-3">
      <div className="flex flex-col items-center">
        <div
          className={clsx(
            "grid size-7 place-items-center rounded-full text-[12px] font-semibold",
            state === "done" && "bg-ok-600 text-white",
            state === "active" && "bg-ink text-white",
            state === "todo" && "bg-canvas text-faint ring-1 ring-line-strong",
          )}
        >
          {index + 1}
        </div>
        <div className="mt-1 w-px flex-1 bg-line" />
      </div>
      <div className={clsx("pb-6", state === "todo" && "opacity-55")}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="text-[14px] font-semibold text-ink">{title}</div>
            <div className="text-[12.5px] text-muted">{caption}</div>
          </div>
          {state === "active" && action}
        </div>
        {children && state !== "todo" && <div className="animate-fade-in mt-3">{children}</div>}
      </div>
    </div>
  );
}

function RecalledList({ items, highlightDoc }: { items: RecalledMemory[]; highlightDoc?: string | null }) {
  return (
    <ol className="space-y-1.5">
      {items.slice(0, 6).map((m) => (
        <li
          key={m.id}
          className={clsx(
            "flex items-start gap-2 rounded-md border px-3 py-2 text-[12.5px]",
            highlightDoc && m.document_id === highlightDoc ? "border-memory-500 bg-memory-50 ring-1 ring-memory-200" : "border-line bg-surface",
          )}
        >
          <span className="mt-px rounded bg-memory-600 px-1.5 font-mono text-[10.5px] font-semibold text-white">{m.ref}</span>
          <span className="flex-1 text-ink">{m.text}</span>
          {highlightDoc && m.document_id === highlightDoc && <Badge tone="memory">New</Badge>}
        </li>
      ))}
    </ol>
  );
}

export default function Demo() {
  const refresh = useRefreshAll();
  const refreshMemory = useRefreshMemory();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [history, setHistory] = useState<MemoryDocument[] | null>(null);
  const [first, setFirst] = useState<Decision | null>(null);
  const [retained, setRetained] = useState<MemoryDocument | null>(null);
  const [newStock, setNewStock] = useState<{ stock: number; demand: number; days: number } | null>(null);
  const [second, setSecond] = useState<Decision | null>(null);

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label);
    try {
      await fn();
      refresh();
    } catch (e) {
      toast.error(`${label} failed`, { description: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };

  const start = () =>
    run("Prepare scenario", async () => {
      await api.demoRun("prepare");
      const mem = await api.memory();
      setHistory(mem.documents.filter((d) => d.medicine_id === "MED-001" && d.origin === "seed"));
      setFirst(null); setRetained(null); setNewStock(null); setSecond(null);
      setStep(1);
    });

  const analyzeFirst = () =>
    run("Agent analysis", async () => {
      const d = await api.analyze("MED-001");
      setFirst(d);
      setStep(2);
    });

  const approve = () =>
    run("Approval", async () => {
      const d = await api.approve(first!.id, {});
      setFirst(d);
      setStep(6);
    });

  const outcome = () =>
    run("Outcome", async () => {
      const qty = first!.final_quantity ?? first!.recommended_quantity;
      const d = await api.outcome(first!.id, { delivered_quantity: qty, delivery_days: first!.planning_lead_days, stockout_occurred: false });
      setFirst(d);
      if (d.retain_error) toast.warning("Outcome recorded, but Hindsight retain failed", { description: d.retain_error });
      const mem = await api.memory();
      setRetained(mem.documents.find((m) => m.document_id === d.retained_document_id) ?? null);
      refreshMemory();
      setStep(7);
    });

  const retryRetain = () =>
    run("Retain", async () => {
      const d = await api.retryRetain(first!.id);
      setFirst(d);
      const mem = await api.memory();
      setRetained(mem.documents.find((m) => m.document_id === d.retained_document_id) ?? null);
      refreshMemory();
    });

  const newSituation = () =>
    run("New situation", async () => {
      const s = await api.demoRun("new_situation");
      setNewStock({ stock: s.medicine.current_stock, demand: s.medicine.daily_demand, days: s.medicine.days_remaining });
      setStep(8);
    });

  const analyzeSecond = () =>
    run("Agent analysis", async () => {
      const d = await api.analyze("MED-001");
      setSecond(d);
      setStep(9);
    });

  const state = (i: number): "done" | "active" | "todo" => (i < step - 1 ? "done" : i === step - 1 ? "active" : "todo");
  const seedDoc = history?.find((d) => d.supplier_id === "SUP-A");
  const hsReady = health.data?.hindsight.connected && health.data.hindsight.seed.state !== "running";
  const newDocUsed = second?.memory_used.some((m) => m.document_id === first?.retained_document_id);

  return (
    <>
      <PageHeader
        title="Memory Demo"
        subtitle="The full memory lifecycle on real services: recall → decide → approve → outcome → retain → better decision."
        actions={
          step > 0 ? (
            <Button onClick={start} disabled={!!busy}>Start over</Button>
          ) : null
        }
      />

      {step === 0 ? (
        <Card className="p-8">
          <div className="max-w-2xl">
            <div className="text-[18px] font-semibold text-ink">Amoxicillin is approaching a stock-out.</div>
            <p className="mt-2 text-[13.5px] leading-relaxed text-ink-2">
              MediStock doesn't only look at today's stock. The agent recalls that Supplier A previously took four days to deliver
              this medicine. With only 2.8 days of inventory left, that experience changes the decision. After the manager approves
              and the delivery succeeds, the outcome is retained — and the next time the same situation occurs the agent uses the
              accumulated experience.
            </p>
            <p className="mt-3 text-[12.5px] text-muted">
              Every step calls the same backend services as the product: the risk engine, the Inventory Decision Agent, Hindsight
              recall and retain, approvals and outcome recording. The demo takes about 2–3 minutes.
            </p>
            {!hsReady && (
              <div className="mt-4 rounded-md border border-med-200 bg-med-50 px-3 py-2 text-[12.5px] text-med-700">
                {health.data?.hindsight.seed.state === "running"
                  ? `Loading historical experience into Hindsight (${health.data.hindsight.seed.done}/${health.data.hindsight.seed.total})…`
                  : "Hindsight is not connected — configure it in backend/.env to run the memory demo."}
              </div>
            )}
            <Button className="mt-5" variant="primary" loading={!!busy} disabled={!hsReady} onClick={start}>
              Run memory demo
            </Button>
          </div>
        </Card>
      ) : (
        <Card className="px-6 pt-6">
          <StepShell index={0} {...STEPS[0]} state={state(0)} action={<Button variant="primary" loading={busy === "Agent analysis"} onClick={analyzeFirst}>Run agent analysis</Button>}>
            {seedDoc ? (
              <div className="rounded-lg border border-memory-200 bg-memory-50/50 p-3.5">
                <div className="flex items-center justify-between">
                  <Badge tone="memory">{seedDoc.category_label}</Badge>
                  <span className="text-[11.5px] text-muted">{fmtDate(seedDoc.occurred_on)} · Hindsight · {seedDoc.document_id}</span>
                </div>
                <p className="mt-2 text-[12.5px] leading-relaxed text-ink-2">{seedDoc.original_text}</p>
              </div>
            ) : (
              <p className="text-[12.5px] text-muted">Historical Amoxicillin experience is not in Hindsight yet — load it from the Memory page.</p>
            )}
          </StepShell>

          <StepShell index={1} {...STEPS[1]} state={state(1)} action={<Button variant="primary" onClick={() => setStep(3)}>Next</Button>}>
            {first && (
              <>
                <div className="mb-2 text-[12.5px] font-medium text-memory-700">
                  Hindsight Recall → {first.memories_recalled.length} relevant memories found
                  {" · "}{first.trace.find((t) => t.tool === "recall_hindsight_memory")?.duration_ms} ms
                </div>
                <RecalledList items={first.memories_recalled} />
              </>
            )}
          </StepShell>

          <StepShell index={2} {...STEPS[2]} state={state(2)} action={<Button variant="primary" onClick={() => setStep(4)}>Next</Button>}>
            {first && (
              <div className="flex flex-wrap items-center gap-6 rounded-lg border border-line p-4">
                <div><div className="text-[11px] text-muted uppercase">Current stock</div><div className="text-[20px] font-semibold tabular">{first.current_stock}</div></div>
                <div><div className="text-[11px] text-muted uppercase">Daily demand</div><div className="text-[20px] font-semibold tabular">{fmtDays(first.daily_demand)}</div></div>
                <div><div className="text-[11px] text-muted uppercase">Days remaining</div><div className="text-[20px] font-semibold text-high-700 tabular">{fmtDays(first.days_remaining)}</div></div>
                <RiskBadge level={first.risk_level} />
                <div className="text-[12.5px] text-muted">
                  Current data alone: primary {first.primary_supplier_name} has a {fmtDays(first.baseline?.lead_days)}-day contracted lead time, which looks safe.
                </div>
              </div>
            )}
          </StepShell>

          <StepShell index={3} {...STEPS[3]} state={state(3)} action={<Button variant="primary" onClick={() => setStep(5)}>Next</Button>}>
            {first && step <= 5 && <DecisionCard decision={first} highlight readOnly />}
            {first && step > 5 && <div className="text-[12.5px] text-muted">{first.headline} — {first.recommended_quantity} units from {first.recommended_supplier_name}.</div>}
          </StepShell>

          <StepShell index={4} {...STEPS[4]} state={state(4)} action={<Button variant="primary" loading={busy === "Approval"} onClick={approve}>Approve recommendation</Button>}>
            {first?.approved_at && (
              <div className="text-[12.5px] text-ink-2">
                Approved · purchase order <span className="font-mono">{first.order_id}</span> raised with {first.final_supplier_name} for {first.final_quantity} units.
              </div>
            )}
          </StepShell>

          <StepShell
            index={5}
            {...STEPS[5]}
            state={state(5)}
            action={
              <Button variant="memory" loading={busy === "Outcome"} onClick={outcome}>
                {busy === "Outcome" ? "Recording & retaining…" : `Record delivery: ${first?.final_quantity ?? ""} units in ${fmtDays(first?.planning_lead_days)} days`}
              </Button>
            }
          >
            {first?.outcome && (
              <div className="flex flex-wrap gap-6 rounded-lg border border-line p-4 text-[13px]">
                <div><div className="text-[11px] text-muted uppercase">{first.final_supplier_name} delivered</div><div className="font-semibold tabular">{first.outcome.delivered_quantity} units</div></div>
                <div><div className="text-[11px] text-muted uppercase">Delivery time</div><div className="font-semibold tabular">{fmtDays(first.outcome.delivery_days)} days</div></div>
                <div><div className="text-[11px] text-muted uppercase">Stock-out</div><div className="font-semibold text-ok-700">Avoided</div></div>
                <div><div className="text-[11px] text-muted uppercase">Outcome</div><Badge tone="ok">{first.outcome.result.toUpperCase()}</Badge></div>
              </div>
            )}
          </StepShell>

          <StepShell
            index={6}
            {...STEPS[6]}
            state={state(6)}
            action={
              first?.retained_document_id ? (
                <Button variant="primary" loading={busy === "New situation"} onClick={newSituation}>Simulate next demand cycle</Button>
              ) : (
                <Button variant="memory" loading={busy === "Retain"} onClick={retryRetain}>Retry Hindsight retain</Button>
              )
            }
          >
            {first?.outcome && !first.retained_document_id && (
              <div className="rounded-lg border border-crit-200 bg-crit-50 px-3 py-2.5 text-[12.5px] text-crit-700">
                The outcome is saved, but Hindsight did not accept the experience. Check the connection and retry.
              </div>
            )}
            {first?.retained_document_id && (
              <div className="rounded-lg border border-memory-200 bg-memory-50/60 p-3.5">
                <div className="text-[13px] font-semibold text-memory-700">Hindsight Retain → New operational experience stored</div>
                <div className="mt-1 text-[11.5px] text-muted">Document {first.retained_document_id}{retained ? ` · ${retained.memory_unit_count} facts extracted by Hindsight` : ""}</div>
                {retained?.original_text && <p className="mt-2 text-[12.5px] leading-relaxed text-ink-2">{retained.original_text}</p>}
              </div>
            )}
          </StepShell>

          <StepShell index={7} {...STEPS[7]} state={state(7)} action={<Button variant="primary" loading={busy === "Agent analysis"} onClick={analyzeSecond}>Run agent analysis again</Button>}>
            {newStock && (
              <div className="flex flex-wrap items-center gap-6 rounded-lg border border-line p-4">
                <div><div className="text-[11px] text-muted uppercase">Current stock</div><div className="text-[20px] font-semibold tabular">{newStock.stock}</div></div>
                <div><div className="text-[11px] text-muted uppercase">Daily demand</div><div className="text-[20px] font-semibold tabular">{fmtDays(newStock.demand)}</div></div>
                <div><div className="text-[11px] text-muted uppercase">Days remaining</div><div className="text-[20px] font-semibold text-high-700 tabular">{fmtDays(newStock.days)}</div></div>
              </div>
            )}
          </StepShell>

          <StepShell index={8} {...STEPS[8]} state={step >= 9 ? "done" : state(8)}>
            {second && (
              <div className="space-y-3">
                <div className={clsx("rounded-lg px-4 py-3 text-[13px]", newDocUsed ? "bg-memory-50 text-memory-700 ring-1 ring-memory-200" : "bg-canvas text-ink-2")}>
                  {newDocUsed
                    ? `The agent recalled and cited the experience retained a moment ago (${first?.retained_document_id}) alongside the historical memories.`
                    : `The agent recalled ${second.memories_recalled.length} memories (${second.memories_recalled.some((m) => m.document_id === first?.retained_document_id) ? "including the new experience" : "Hindsight may still be indexing the new experience"}).`}
                </div>
                {second.memories_recalled.length > 0 && <RecalledList items={second.memories_recalled} highlightDoc={first?.retained_document_id} />}
                <DecisionCard decision={second} highlight />
                <p className="text-[12px] text-muted">
                  This recommendation stays pending in the Agent Decision Center, where it can be approved, modified or rejected like any other.
                </p>
              </div>
            )}
          </StepShell>
          {busy && busy !== "Outcome" && (
            <div className="mb-6 flex items-center gap-2 text-[12.5px] text-muted"><Loader2 className="size-3.5 animate-spin" />{busy}…</div>
          )}
        </Card>
      )}
    </>
  );
}
