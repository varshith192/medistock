export type RiskLevel = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export interface Medicine {
  id: string;
  name: string;
  generic_name: string;
  form: string;
  category: string;
  current_stock: number;
  daily_demand: number;
  pack_size: number;
  unit_cost: number;
  expiry_date: string;
  batch_no: string;
  storage: string;
  primary_supplier_id: string;
  primary_supplier_name: string | null;
  approved_supplier_ids: string[];
  essential: number;
  days_remaining: number;
  risk_level: RiskLevel;
  days_to_expiry: number;
  expiry_risk: boolean;
  units_at_expiry_risk: number;
  supplier_risk: boolean;
  agent_status: "Action Required" | "Decision Pending" | "Awaiting Delivery" | "Monitor" | "Healthy";
  active_decision_id: string | null;
}

export interface HistoryPoint {
  day: string;
  closing_stock: number;
  dispensed: number;
  received: number;
}

export interface Order {
  id: string;
  medicine_id: string;
  supplier_id: string;
  supplier_name?: string;
  medicine_name?: string;
  quantity: number;
  ordered_at: string;
  expected_days: number;
  actual_days: number | null;
  delivered_qty: number | null;
  status: "delivered" | "delivered_late" | "in_transit" | "cancelled";
  urgency: "routine" | "urgent" | "emergency";
  decision_id: string | null;
}

export interface SupplierTerms {
  id: string;
  name: string;
  legal_name: string;
  contracted_lead_days: number;
  min_order_qty: number;
  is_primary: boolean;
  open_orders: { id: string; quantity: number; ordered_at: string; expected_days: number }[];
}

export interface MedicineSupplierPerf {
  supplier_id: string;
  supplier_name: string;
  orders: number;
  avg_delivery_days: number;
  expected_delivery_days: number;
  worst_delivery_days: number;
  on_time_pct: number;
}

export interface Incident {
  id: string;
  medicine_id: string;
  medicine_name: string;
  type: "stock_out" | "stock_out_risk" | "supplier_delay" | "expiry" | "emergency_replenishment" | "demand_spike";
  title: string;
  severity: "critical" | "high" | "medium" | "low";
  occurred_at: string;
  cause: string;
  action: string;
  supplier_id: string | null;
  supplier_name: string | null;
  outcome: string;
  status: "open" | "monitoring" | "resolved";
  decision_id: string | null;
  memory_document_id: string | null;
  memory_status: "retained" | "pending" | "not_retained" | "failed";
}

export interface RecalledMemory {
  ref: string;
  id: string;
  text: string;
  fact_type: string | null;
  occurred_start: string | null;
  mentioned_at: string | null;
  document_id: string | null;
  tags: string[];
  metadata: Record<string, string>;
  category: string;
  medicine_id: string | null;
  supplier_id: string | null;
  score: number | null;
  source: "hindsight";
}

export interface MemoryUsed {
  ref: string;
  influence: string;
  text: string;
  memory_id: string;
  document_id: string | null;
  category: string;
  occurred: string;
  experience?: string | null;
}

export interface TraceStep {
  tool: string;
  label: string;
  summary: string;
  status: "ok" | "error";
  duration_ms: number;
}

export interface TimelineStep {
  key: string;
  label: string;
  done: boolean;
  at: string | null;
  detail?: string | null;
}

export interface Outcome {
  result: "successful" | "delayed" | "failed";
  delivered_quantity: number;
  delivery_days: number;
  stockout_occurred?: boolean;
  stockout: string;
  expected_days?: number;
  notes?: string | null;
  summary: string;
}

export interface Decision {
  id: string;
  medicine_id: string;
  medicine_name: string;
  generic_name: string;
  category: string;
  pack_size: number;
  created_at: string;
  status: "pending" | "approved" | "rejected" | "completed" | "superseded";
  source: "agent" | "manual";
  risk_level: RiskLevel;
  days_remaining: number;
  current_stock: number;
  daily_demand: number;
  recommended_supplier_id: string;
  recommended_supplier_name: string;
  recommended_quantity: number;
  planning_lead_days: number;
  primary_supplier_id: string;
  primary_supplier_name: string;
  final_supplier_id: string | null;
  final_supplier_name: string | null;
  final_quantity: number | null;
  urgency: "emergency" | "urgent" | "routine";
  confidence: "high" | "medium" | "low";
  headline: string;
  assessment: string;
  reason: string;
  why: string[];
  memory_used: MemoryUsed[];
  memories_recalled: RecalledMemory[];
  alternatives: { supplier_id: string; supplier_name: string; why_not: string }[];
  baseline: {
    supplier_id: string;
    supplier_name: string;
    quantity: number;
    lead_days: number;
    headline: string;
    reason: string;
    arrives_before_stockout: boolean;
  } | null;
  memory_state: "found" | "none_found" | "unavailable" | null;
  recall_query: string | null;
  engine: string;
  trace: TraceStep[];
  order_id: string | null;
  manager_note: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  outcome: Outcome | null;
  outcome_at: string | null;
  retained_document_id: string | null;
  timeline: TimelineStep[];
}

export interface MedicineDetail {
  medicine: Medicine;
  demand_trend: { recent_avg: number; prior_avg: number; change_pct: number };
  history: HistoryPoint[];
  orders: Order[];
  supplier_performance: MedicineSupplierPerf[];
  approved_suppliers: SupplierTerms[];
  incidents: Incident[];
  decisions: (Decision & { recommended_supplier_name: string; final_supplier_name: string | null })[];
}

export interface Supplier {
  id: string;
  name: string;
  legal_name: string;
  city: string;
  contracted_lead_days: number;
  min_order_qty: number;
  contact_email: string;
  phone: string;
  orders: number;
  avg_delivery_days: number | null;
  expected_delivery_days: number;
  on_time_pct: number;
  delay_rate_pct: number;
  delay_rate_label: "High" | "Medium" | "Low";
  reliability: "Reliable" | "Watch" | "Needs Attention" | "No history";
  primary_for: string[];
  approved_for_count: number;
  by_medicine: { medicine: string; orders: number; avg_days: number; expected_days: number; worst_days: number; on_time_pct: number }[];
  recent_orders: Order[];
}

export interface AgentEvent {
  id: number;
  ts: string;
  kind: "detect" | "recall" | "retain" | "recommend" | "approve" | "modify" | "reject" | "outcome" | "system" | "error";
  title: string;
  detail: string | null;
  medicine_id: string | null;
  medicine_name: string | null;
  decision_id: string | null;
  meta: Record<string, unknown> | null;
}

export interface OverviewData {
  metrics: {
    total_medicines: number;
    stock_risks: number;
    critical: number;
    high: number;
    expiry_risks: number;
    expiry_threshold_days: number;
    pending_decisions: number;
    awaiting_outcome: number;
    supplier_issues: number;
    decisions_completed: number;
    success_rate: number | null;
    experiences_retained: number;
    memory_influenced_decisions_7d: number;
  };
  stock_risks: Medicine[];
  expiry_risks: Medicine[];
  supplier_issues: { id: string; name: string; legal_name: string; avg_delivery_days: number; expected_delivery_days: number; on_time_pct: number }[];
  overdue_orders: (Order & { elapsed_days: number; overdue: boolean })[];
  open_incidents: Incident[];
  risk_distribution: Record<RiskLevel, number>;
}

export interface MemoryFact {
  id: string;
  text: string;
  fact_type: string | null;
  occurred_start: string | null;
  mentioned_at: string | null;
  entities: string | null;
  proof_count: number | null;
}

export interface MemoryDocument {
  document_id: string;
  category: string;
  category_label: string;
  origin: "seed" | "agent" | "external" | string;
  medicine_id: string | null;
  medicine_name: string | null;
  supplier_id: string | null;
  supplier_name: string | null;
  occurred_on: string | null;
  outcome: string | null;
  actual_delivery_days: string | null;
  expected_delivery_days: string | null;
  created_at: string | null;
  memory_unit_count: number;
  original_text: string | null;
  tags: string[];
  facts: MemoryFact[];
}

export interface MemoryOverview {
  bank_id: string;
  base_url: string;
  documents: MemoryDocument[];
  totals: { documents: number; facts: number; fact_types: Record<string, number> };
  categories: { key: string; label: string; count: number }[];
}

export interface RecallResult {
  query: string;
  items: RecalledMemory[];
  duration_ms: number;
  total_results: number;
}

export interface SeedState {
  state: "idle" | "running" | "done" | "error";
  done: number;
  total: number;
  error: string | null;
  current: string | null;
}

export interface Health {
  database: { ok: boolean; medicines?: number; error?: string };
  agent: { configured: boolean; model: string; provider: string; ok: boolean | null; error: string | null };
  hindsight: {
    connected: boolean;
    configured: boolean;
    error: string | null;
    latency_ms?: number | null;
    bank_id: string;
    base_url: string;
    seed: SeedState;
  };
}

export interface AppSettings {
  expiry_threshold_days: number;
  target_cover_days: number;
  risk_rules: Record<RiskLevel, string>;
  llm_model: string;
  hindsight_base_url: string;
  hindsight_bank_id: string;
}

export interface DemoState {
  medicine: Medicine;
  decisions: { id: string; status: string; created_at: string; recommended_supplier_id: string; retained_document_id: string | null }[];
  agent_memories: { document_id: string; origin: string; category: string; retained_at: string }[];
  seed: SeedState;
}
