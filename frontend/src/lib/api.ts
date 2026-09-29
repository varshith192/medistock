import type {
  AgentEvent, AppSettings, Decision, DemoState, Health, Incident, Medicine, MedicineDetail, MemoryOverview,
  OverviewData, RecallResult, SeedState, Supplier,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "Cannot reach the MediStock backend. Is it running on port 8000?");
  }
  if (!res.ok) {
    let body: { detail?: unknown } | null = null;
    try {
      body = await res.json();
    } catch {
      /* not a JSON error from the API */
    }
    if (!body && res.status >= 500) {
      // The dev-server proxy answers with a bare 5xx when the backend is down.
      throw new ApiError(0, "Cannot reach the MediStock backend. Is it running on port 8000?");
    }
    let message = `Request failed (${res.status})`;
    if (typeof body?.detail === "string") message = body.detail;
    else if (Array.isArray(body?.detail))
      message = body.detail.map((d: { loc?: string[]; msg: string }) => `${d.loc?.at(-1) ?? "value"}: ${d.msg}`).join("; ");
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  health: () => request<Health>("/health"),
  overview: () => request<OverviewData>("/overview"),
  inventory: () => request<Medicine[]>("/inventory"),
  medicine: (id: string) => request<MedicineDetail>(`/inventory/${id}`),
  suppliers: () => request<Supplier[]>("/suppliers"),
  incidents: () => request<Incident[]>("/incidents"),
  events: (limit = 30, kinds?: string) =>
    request<AgentEvent[]>(`/events?limit=${limit}${kinds ? `&kinds=${kinds}` : ""}`),
  decisions: (status?: string, medicineId?: string) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (medicineId) params.set("medicine_id", medicineId);
    const qs = params.toString();
    return request<Decision[]>(`/decisions${qs ? `?${qs}` : ""}`);
  },
  analyze: (medicineId: string) => post<Decision>("/agent/analyze", { medicine_id: medicineId }),
  approve: (id: string, body: { supplier_id?: string; quantity?: number; note?: string }) =>
    post<Decision>(`/decisions/${id}/approve`, body),
  reject: (id: string, reason?: string) => post<Decision>(`/decisions/${id}/reject`, { reason }),
  outcome: (id: string, body: { delivered_quantity: number; delivery_days: number; stockout_occurred: boolean; notes?: string }) =>
    post<Decision & { retain_error: string | null }>(`/decisions/${id}/outcome`, body),
  retryRetain: (id: string) => post<Decision>(`/decisions/${id}/retain`),
  memory: () => request<MemoryOverview>("/memory"),
  recall: (query: string) => post<RecallResult>("/memory/recall", { query }),
  seedMemory: () => post<SeedState>("/memory/seed"),
  settings: () => request<AppSettings>("/settings"),
  saveSettings: (body: Partial<Pick<AppSettings, "expiry_threshold_days" | "target_cover_days">>) =>
    request<AppSettings>("/settings", { method: "PUT", body: JSON.stringify(body) }),
  demoRun: (action: "prepare" | "new_situation", medicineId = "MED-001") =>
    post<DemoState>("/demo/run", { action, medicine_id: medicineId }),
  demoReset: () => post<{ removed_memories: number }>("/demo/reset"),
};
