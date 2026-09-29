import { useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

/** Refresh every view that depends on operational state after a mutation. */
export function useRefreshAll() {
  const qc = useQueryClient();
  return useCallback(() => {
    for (const key of ["overview", "inventory", "decisions", "decision", "events", "incidents", "suppliers", "medicine", "demo", "health"]) {
      qc.invalidateQueries({ queryKey: [key] });
    }
  }, [qc]);
}

export function useRefreshMemory() {
  const qc = useQueryClient();
  return useCallback(() => qc.invalidateQueries({ queryKey: ["memory"] }), [qc]);
}
