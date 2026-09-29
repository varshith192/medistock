import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { api } from "../lib/api";
import { fmtShortDate, fmtTime } from "../lib/format";
import type { AgentEvent } from "../lib/types";
import { EmptyState, ErrorState, SkeletonRows } from "./ui";

/** Status dot colour per event type. */
const DOT: Record<AgentEvent["kind"], string> = {
  detect: "bg-high-600",
  recall: "bg-memory-500",
  retain: "bg-memory-600",
  recommend: "bg-brand-600",
  approve: "bg-ok-600",
  modify: "bg-ok-600",
  reject: "bg-faint",
  outcome: "bg-ok-600",
  system: "bg-line-strong",
  error: "bg-crit-600",
};

export function ActivityFeed({ limit = 20, kinds, compact }: { limit?: number; kinds?: string; compact?: boolean }) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["events", limit, kinds],
    queryFn: () => api.events(limit, kinds),
    refetchInterval: 5000,
  });
  if (isLoading) return <SkeletonRows rows={5} />;
  if (error) return <div className="p-4"><ErrorState error={error} onRetry={() => refetch()} /></div>;
  if (!data?.length) return <EmptyState title="No agent activity yet" description="Run an agent analysis to see detections, memory operations and recommendations here." />;
  const today = new Date().toDateString();
  return (
    <ol className="divide-y divide-line">
      {data.map((e) => {
        const isToday = new Date(e.ts).toDateString() === today;
        return (
          <li key={e.id} className={clsx("grid grid-cols-[52px_12px_1fr] items-start gap-2 px-4", compact ? "py-2" : "py-2.5")}>
            <div className="pt-1 text-[12px] font-medium text-muted tabular">
              {fmtTime(e.ts)}
              {!isToday && <div className="text-[10.5px] font-normal text-faint">{fmtShortDate(e.ts)}</div>}
            </div>
            <span className={clsx("mt-[7px] size-2 rounded-full", DOT[e.kind] ?? DOT.system)} />
            <div className="min-w-0">
              <div className={clsx("text-[13px] font-medium", e.kind === "recall" || e.kind === "retain" ? "text-memory-700" : "text-ink")}>{e.title}</div>
              {e.detail && <div className="truncate text-[12px] text-muted">{e.detail}</div>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
