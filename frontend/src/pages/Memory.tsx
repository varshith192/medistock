import { useMutation, useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { ChevronDown, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { ActivityFeed } from "../components/ActivityFeed";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, inputClass, PageHeader, Skeleton } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { capitalize, fmtDate, MEMORY_CATEGORY } from "../lib/format";
import { useRefreshAll, useRefreshMemory } from "../lib/hooks";
import type { MemoryDocument, RecallResult } from "../lib/types";

const OUTCOME_TONE: Record<string, "ok" | "med" | "crit" | "neutral"> = {
  successful: "ok", reliable: "ok", stock_maintained: "ok", delayed: "med", mixed: "med", write_off: "crit", failed: "crit", rejected: "neutral",
};

function MedicineKnowledge({ docs }: { docs: MemoryDocument[] }) {
  const groups = useMemo(() => {
    const map = new Map<string, { name: string; items: MemoryDocument[] }>();
    docs.filter((d) => d.medicine_name && d.supplier_name && d.actual_delivery_days).forEach((d) => {
      const g = map.get(d.medicine_id!) ?? { name: d.medicine_name!, items: [] };
      g.items.push(d);
      map.set(d.medicine_id!, g);
    });
    return Array.from(map.values()).sort((a, b) => b.items.length - a.items.length);
  }, [docs]);
  if (!groups.length) return null;
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {groups.map((g) => {
        const sorted = [...g.items].sort((a, b) => (a.occurred_on ?? "").localeCompare(b.occurred_on ?? ""));
        const latest = sorted[sorted.length - 1];
        return (
          <Card key={g.name} className="p-4">
            <div className="flex items-center justify-between">
              <div className="text-[13.5px] font-semibold tracking-wide uppercase">{g.name}</div>
              <Badge tone="memory">{g.items.length} {g.items.length === 1 ? "experience" : "experiences"}</Badge>
            </div>
            <div className="mt-3 space-y-2">
              {sorted.map((d) => (
                <div key={d.document_id} className="grid grid-cols-[90px_1fr_auto] items-center gap-2 text-[12.5px]">
                  <span className="font-medium text-ink">{d.supplier_name}</span>
                  <span className="text-ink-2">
                    Delivered in <b className="tabular">{d.actual_delivery_days} days</b>
                    {d.expected_delivery_days && <span className="text-muted"> vs {d.expected_delivery_days}d contract</span>}
                  </span>
                  <Badge tone={OUTCOME_TONE[d.outcome ?? ""] ?? "neutral"}>{capitalize((d.outcome ?? "").replace("_", " "))}</Badge>
                </div>
              ))}
            </div>
            <div className="mt-3 border-t border-line pt-2 text-[11.5px] text-muted">
              Latest: {fmtDate(latest.occurred_on ?? latest.created_at)} · Source: Hindsight
            </div>
          </Card>
        );
      })}
    </div>
  );
}

function MemoryCard({ doc }: { doc: MemoryDocument }) {
  const [open, setOpen] = useState(false);
  const title = doc.medicine_name ?? doc.supplier_name ?? MEMORY_CATEGORY[doc.category] ?? "Operational memory";
  return (
    <Card className="flex flex-col">
      <div className="flex items-start justify-between gap-2 px-4 pt-3.5">
        <div>
          <div className="text-[13px] font-semibold tracking-wide text-ink uppercase">{title}</div>
          <div className="mt-1 flex flex-wrap gap-1.5">
            <Badge tone="memory">{doc.category_label}</Badge>
            {doc.origin === "agent" ? <Badge tone="brand">Retained by agent</Badge> : doc.origin === "seed" ? <Badge>Historical record</Badge> : null}
            {doc.outcome && <Badge tone={OUTCOME_TONE[doc.outcome] ?? "neutral"}>{capitalize(doc.outcome.replace("_", " "))}</Badge>}
          </div>
        </div>
        <span className="shrink-0 text-[11.5px] text-muted">{fmtDate(doc.occurred_on ?? doc.created_at)}</span>
      </div>
      {doc.supplier_name && doc.actual_delivery_days && (
        <div className="mx-4 mt-3 grid grid-cols-2 gap-2 rounded-md bg-canvas px-3 py-2 text-[12px]">
          <div><div className="text-muted">Supplier</div><div className="font-medium">{doc.supplier_name}</div></div>
          <div><div className="text-muted">Actual delivery</div><div className="font-medium tabular">{doc.actual_delivery_days} days{doc.expected_delivery_days ? ` (contract ${doc.expected_delivery_days}d)` : ""}</div></div>
        </div>
      )}
      <p className="flex-1 px-4 pt-3 text-[12.5px] leading-relaxed text-ink-2">{doc.original_text}</p>
      <div className="px-4 pt-2">
        <button onClick={() => setOpen((v) => !v)} className="flex items-center gap-1 text-[12px] font-medium text-memory-700 hover:underline">
          <ChevronDown className={clsx("size-3.5 transition-transform", open && "rotate-180")} />
          {doc.facts.length} facts extracted by Hindsight
        </button>
        {open && (
          <ul className="mt-2 space-y-1.5 border-l-2 border-memory-200 pl-3">
            {doc.facts.map((f) => (
              <li key={f.id} className="text-[12px] text-ink-2">
                {f.text}
                <span className="ml-1.5 text-[10.5px] text-faint">{f.fact_type}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="mt-3 flex items-center justify-between border-t border-line px-4 py-2 text-[11px] text-faint">
        <span>Source: Hindsight · {doc.document_id}</span>
        <span>retained {fmtDate(doc.created_at)}</span>
      </div>
    </Card>
  );
}

function RecallExplorer() {
  const [query, setQuery] = useState("Amoxicillin supplier delivery delays and outcomes");
  const refresh = useRefreshAll();
  const recall = useMutation({
    mutationFn: (q: string) => api.recall(q),
    onSuccess: () => refresh(),
    onError: (e: Error) => toast.error("Recall failed", { description: e.message }),
  });
  const result: RecallResult | undefined = recall.data;
  return (
    <Card>
      <CardHeader title="Recall explorer" subtitle="Query Hindsight exactly as the agent does before each decision" />
      <form
        className="flex gap-2 px-4 pt-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (query.trim().length >= 3) recall.mutate(query.trim());
        }}
      >
        <div className="relative flex-1">
          <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-faint" />
          <input className={clsx(inputClass, "pl-8")} value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <Button type="submit" variant="memory" loading={recall.isPending}>Recall</Button>
      </form>
      <div className="px-4 py-3">
        {!result && !recall.isPending && <p className="text-[12.5px] text-muted">Results show the facts Hindsight returns, ranked by relevance.</p>}
        {recall.isPending && <div className="space-y-2"><Skeleton className="h-10" /><Skeleton className="h-10" /><Skeleton className="h-10" /></div>}
        {result && (
          <>
            <div className="mb-2 text-[12px] text-memory-700">Hindsight Recall → {result.items.length} relevant memories found · {result.duration_ms} ms</div>
            <ol className="space-y-1.5">
              {result.items.map((m) => (
                <li key={m.id} className="rounded-md border border-line px-3 py-2 text-[12.5px]">
                  <div className="flex items-start gap-2">
                    <span className="mt-px rounded bg-memory-600 px-1.5 font-mono text-[10.5px] font-semibold text-white">{m.ref}</span>
                    <span className="flex-1 text-ink">{m.text}</span>
                  </div>
                  <div className="mt-1 pl-8 text-[11px] text-faint">
                    {m.fact_type} · {MEMORY_CATEGORY[m.category] ?? m.category}{m.document_id ? ` · ${m.document_id}` : ""}
                    {(m.occurred_start || m.mentioned_at) && ` · ${fmtDate((m.occurred_start || m.mentioned_at)!.slice(0, 10))}`}
                  </div>
                </li>
              ))}
            </ol>
          </>
        )}
      </div>
    </Card>
  );
}

export default function Memory() {
  const refreshMemory = useRefreshMemory();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 5000 });
  const configured = health.data?.hindsight.configured === true;
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["memory"], queryFn: api.memory, retry: 0, staleTime: 60000, enabled: configured,
  });
  const [category, setCategory] = useState<string>("ALL");
  const seed = useMutation({
    mutationFn: api.seedMemory,
    onSuccess: () => { toast.success("Historical experience loaded into Hindsight"); refreshMemory(); },
    onError: (e: Error) => toast.error("Seeding failed", { description: e.message }),
  });
  const seedState = health.data?.hindsight.seed;
  const docs = (data?.documents ?? []).filter((d) => category === "ALL" || d.category === category);
  const notConfigured = (health.data && !configured) || (error instanceof ApiError && error.status === 503);

  return (
    <>
      <PageHeader title="Operational Memory" subtitle="MediStock's accumulated experience from inventory decisions and outcomes." />

      <Card className="mb-5 flex flex-wrap items-center gap-x-8 gap-y-3 px-5 py-4">
        <div className="flex items-center gap-3">
          <div>
            <div className="text-[13.5px] font-semibold">Hindsight memory bank</div>
            <div className="font-mono text-[11.5px] text-muted">{health.data?.hindsight.bank_id ?? "…"} · {health.data?.hindsight.base_url.replace("https://", "")}</div>
          </div>
        </div>
        <div className="flex gap-8">
          <div><div className="text-[11px] text-muted uppercase">Experiences</div><div className="text-[18px] font-semibold tabular">{data?.totals.documents ?? "—"}</div></div>
          <div><div className="text-[11px] text-muted uppercase">Extracted facts</div><div className="text-[18px] font-semibold tabular">{data?.totals.facts ?? "—"}</div></div>
          <div><div className="text-[11px] text-muted uppercase">Retained by agent</div><div className="text-[18px] font-semibold tabular">{data ? data.documents.filter((d) => d.origin === "agent").length : "—"}</div></div>
        </div>
        <div className="ml-auto flex items-center gap-2 text-[12.5px]">
          {seedState?.state === "running" && <Badge tone="med">Loading history {seedState.done}/{seedState.total}</Badge>}
          <span className={clsx("size-2 rounded-full", health.data?.hindsight.connected ? "bg-ok-600" : "bg-crit-600")} />
          {health.data?.hindsight.connected ? `Connected${health.data.hindsight.latency_ms ? ` · ${health.data.hindsight.latency_ms} ms` : ""}` : "Not connected"}
          <Button size="sm" onClick={() => refetch()}>Refresh</Button>
        </div>
      </Card>

      {notConfigured ? (
        <Card>
          <EmptyState
            title="Hindsight is not configured"
            description="Add HINDSIGHT_API_KEY (and optionally HINDSIGHT_BASE_URL) to backend/.env, then restart the backend. MediStock never shows memories that did not come from Hindsight."
          />
        </Card>
      ) : error ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : (
        <>
          <div className="mb-3 flex flex-wrap gap-1.5">
            <button onClick={() => setCategory("ALL")} className={clsx("rounded-full px-3 py-1 text-[12.5px] font-medium ring-1", category === "ALL" ? "bg-ink text-white ring-ink" : "bg-surface text-ink-2 ring-line-strong hover:bg-canvas")}>
              All <span className="ml-1 opacity-60 tabular">{data?.totals.documents ?? 0}</span>
            </button>
            {(data?.categories ?? []).map((c) => (
              <button key={c.key} onClick={() => setCategory(c.key)} className={clsx("rounded-full px-3 py-1 text-[12.5px] font-medium ring-1", category === c.key ? "bg-memory-600 text-white ring-memory-600" : "bg-surface text-ink-2 ring-line-strong hover:bg-canvas")}>
                {c.label} <span className="ml-1 opacity-60 tabular">{c.count}</span>
              </button>
            ))}
          </div>

          {isLoading || !health.data ? (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-56" />)}</div>
          ) : data && data.documents.length === 0 ? (
            <Card>
              <EmptyState
                title="The memory bank is empty"
                description="Load the pharmacy's historical incidents and decisions into Hindsight so the agent has experience to recall."
                action={<Button variant="memory" loading={seed.isPending || seedState?.state === "running"} onClick={() => seed.mutate()}>Load historical experience</Button>}
              />
            </Card>
          ) : (
            <>
              {category === "ALL" && data && (
                <>
                  <h2 className="mb-3 text-[12px] font-semibold tracking-wider text-muted uppercase">Supplier delivery knowledge by medicine</h2>
                  <MedicineKnowledge docs={data.documents} />
                  <h2 className="mt-7 mb-3 text-[12px] font-semibold tracking-wider text-muted uppercase">All retained experiences</h2>
                </>
              )}
              {docs.length === 0 ? (
                <Card><EmptyState title={`No ${MEMORY_CATEGORY[category] ?? "memories"} yet`} /></Card>
              ) : (
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{docs.map((d) => <MemoryCard key={d.document_id} doc={d} />)}</div>
              )}
            </>
          )}

          <div className="mt-7 grid gap-4 xl:grid-cols-2">
            <RecallExplorer />
            <Card>
              <CardHeader title="Memory operations log" subtitle="Every Hindsight recall and retain performed by MediStock" />
              <ActivityFeed limit={12} kinds="recall,retain" compact />
            </Card>
          </div>
        </>
      )}
    </>
  );
}
