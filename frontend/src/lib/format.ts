export const fmtDays = (value: number | null | undefined, digits = 1) => {
  if (value === null || value === undefined) return "—";
  if (value >= 999) return "∞";
  return `${Number(value.toFixed(digits))}`;
};

export const fmtNum = (value: number | null | undefined) =>
  value === null || value === undefined ? "—" : value.toLocaleString("en-IN");

const toDate = (value: string) => new Date(value.length === 10 ? `${value}T00:00:00` : value);

export const fmtDate = (value: string | null | undefined) =>
  value ? toDate(value).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "—";

export const fmtShortDate = (value: string | null | undefined) =>
  value ? toDate(value).toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : "—";

export const fmtTime = (value: string | null | undefined) =>
  value ? toDate(value).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "—";

export const fmtDateTime = (value: string | null | undefined) =>
  value ? `${fmtShortDate(value)}, ${fmtTime(value)}` : "—";

export function fmtRelative(value: string | null | undefined) {
  if (!value) return "—";
  const diff = (Date.now() - toDate(value).getTime()) / 1000;
  if (diff < 45) return "just now";
  if (diff < 3600) return `${Math.round(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)} h ago`;
  const days = Math.round(diff / 86400);
  return days === 1 ? "yesterday" : `${days} days ago`;
}

export const INCIDENT_TYPE: Record<string, string> = {
  stock_out: "Stock-out",
  stock_out_risk: "Stock-out risk",
  supplier_delay: "Supplier delay",
  expiry: "Expiry risk",
  emergency_replenishment: "Emergency replenishment",
  demand_spike: "Demand spike",
};

export const MEMORY_CATEGORY: Record<string, string> = {
  supplier_knowledge: "Supplier Knowledge",
  medicine_pattern: "Medicine Patterns",
  stock_out_incident: "Stock-Out Incidents",
  replenishment_decision: "Replenishment Decisions",
  expiry_incident: "Expiry Incidents",
  manager_feedback: "Manager Feedback",
  successful_outcome: "Successful Outcomes",
};

export const TOOL_LABEL: Record<string, string> = {
  get_medicine_details: "get_medicine_details()",
  calculate_stock_risk: "calculate_stock_risk()",
  get_supplier_terms: "get_supplier_terms()",
  recall_hindsight_memory: "recall_hindsight_memory()",
  create_replenishment_recommendation: "create_replenishment_recommendation()",
  validate_recommendation: "validate_recommendation()",
  store_decision: "store_decision()",
};

export const capitalize = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
