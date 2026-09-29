import { useMutation, useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { fmtDays } from "../../lib/format";
import { useRefreshAll, useRefreshMemory } from "../../lib/hooks";
import type { Decision } from "../../lib/types";
import { Button, Field, inputClass, Modal, RiskBadge } from "../ui";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[132px_1fr] gap-3 border-b border-line py-2 text-[13px] last:border-0">
      <div className="text-muted">{label}</div>
      <div className="text-ink">{children}</div>
    </div>
  );
}

export function ApproveDialog({
  decision,
  mode,
  open,
  onClose,
}: {
  decision: Decision;
  mode: "approve" | "modify";
  open: boolean;
  onClose: () => void;
}) {
  const refresh = useRefreshAll();
  const [supplierId, setSupplierId] = useState(decision.recommended_supplier_id);
  const [quantity, setQuantity] = useState(decision.recommended_quantity);
  const [note, setNote] = useState("");
  const { data: detail } = useQuery({
    queryKey: ["medicine", decision.medicine_id],
    queryFn: () => api.medicine(decision.medicine_id),
    enabled: open && mode === "modify",
  });
  useEffect(() => {
    if (open) {
      setSupplierId(decision.recommended_supplier_id);
      setQuantity(decision.recommended_quantity);
      setNote("");
    }
  }, [open, decision]);

  const mutation = useMutation({
    mutationFn: () =>
      api.approve(decision.id, mode === "modify" ? { supplier_id: supplierId, quantity, note: note || undefined } : {}),
    onSuccess: (d) => {
      toast.success(`${d.id} approved`, { description: `${d.final_quantity} units of ${d.medicine_name} ordered from ${d.final_supplier_name} (${d.order_id})` });
      refresh();
      onClose();
    },
    onError: (e: Error) => toast.error("Approval failed", { description: e.message }),
  });

  const modified = supplierId !== decision.recommended_supplier_id || quantity !== decision.recommended_quantity;
  const supplierName =
    detail?.approved_suppliers.find((s) => s.id === supplierId)?.name ?? decision.recommended_supplier_name;

  return (
    <Modal
      open={open}
      onClose={onClose}
      width="max-w-xl"
      title={mode === "modify" ? "Modify and approve replenishment" : "Confirm replenishment decision"}
      subtitle={`${decision.id} · creates a purchase order and waits for the delivery outcome`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button
            variant="primary"
            loading={mutation.isPending}
            disabled={mode === "modify" && (!quantity || quantity <= 0)}
            onClick={() => mutation.mutate()}
          >
            {mode === "modify" && modified ? "Approve with changes" : "Confirm approval"}
          </Button>
        </>
      }
    >
      {mode === "modify" && (
        <div className="mb-4 grid grid-cols-2 gap-3">
          <Field label="Supplier">
            <select className={inputClass} value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
              {(detail?.approved_suppliers ?? [{ id: decision.recommended_supplier_id, name: decision.recommended_supplier_name, contracted_lead_days: 0, is_primary: false }]).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}{s.contracted_lead_days ? ` · ${s.contracted_lead_days}d contract` : ""}{s.is_primary ? " · primary" : ""}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Quantity (units)" hint={`Pack size ${decision.pack_size}`}>
            <input
              type="number"
              min={1}
              className={inputClass}
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
            />
          </Field>
          <div className="col-span-2">
            <Field label="Reason for change" hint="Kept with the decision and retained with its outcome as manager feedback.">
              <input className={inputClass} placeholder="e.g. Budget cap for this week" value={note} onChange={(e) => setNote(e.target.value)} />
            </Field>
          </div>
        </div>
      )}
      <div className="rounded-lg border border-line px-3">
        <Row label="Medicine">{decision.medicine_name}</Row>
        <Row label="Quantity">
          <span className="font-semibold tabular">{quantity} units</span>
          {mode === "modify" && quantity !== decision.recommended_quantity && (
            <span className="ml-2 text-muted">(recommended {decision.recommended_quantity})</span>
          )}
        </Row>
        <Row label="Supplier">
          <span className="font-semibold">{supplierName}</span>
          {supplierId !== decision.recommended_supplier_id && (
            <span className="ml-2 text-muted">(recommended {decision.recommended_supplier_name})</span>
          )}
        </Row>
        <Row label="Risk">
          <span className="inline-flex items-center gap-2">
            <RiskBadge level={decision.risk_level} />
            {fmtDays(decision.days_remaining)} days of cover · {decision.current_stock} units at {fmtDays(decision.daily_demand)}/day
          </span>
        </Row>
        <Row label="Reason">{decision.reason}</Row>
      </div>
      {decision.memory_used.length > 0 && (
        <div className="mt-3 rounded-lg border border-memory-200 bg-memory-50/60 px-3 py-2.5">
          <div className="mb-1.5 text-[12px] font-semibold text-memory-700">Historical context from Hindsight</div>
          <ul className="space-y-1">
            {decision.memory_used.map((m) => (
              <li key={m.ref} className="text-[12.5px] text-ink-2">
                <span className="mr-1.5 font-mono text-[11px] text-memory-600">{m.ref}</span>
                {m.influence || m.text}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Modal>
  );
}

export function RejectDialog({ decision, open, onClose }: { decision: Decision; open: boolean; onClose: () => void }) {
  const refresh = useRefreshAll();
  const refreshMemory = useRefreshMemory();
  const [reason, setReason] = useState("");
  useEffect(() => {
    if (open) setReason("");
  }, [open]);
  const mutation = useMutation({
    mutationFn: () => api.reject(decision.id, reason || undefined),
    onSuccess: (d) => {
      toast.success(`${d.id} rejected`, {
        description: d.retained_document_id ? "Manager feedback retained in Hindsight." : "No reason given, so nothing was retained.",
      });
      refresh();
      refreshMemory();
      onClose();
    },
    onError: (e: Error) => toast.error("Rejection failed", { description: e.message }),
  });
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Reject recommendation"
      subtitle={`${decision.medicine_name} · ${decision.headline}`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="danger" loading={mutation.isPending} onClick={() => mutation.mutate()}>
            Reject recommendation
          </Button>
        </>
      }
    >
      <Field
        label="Reason"
        hint="The reason is retained in Hindsight as manager feedback and informs future recommendations."
      >
        <textarea
          rows={3}
          className={clsx(inputClass, "h-auto py-2")}
          placeholder="e.g. Supplier B is on credit hold this month"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </Field>
    </Modal>
  );
}

export function OutcomeDialog({ decision, open, onClose }: { decision: Decision; open: boolean; onClose: () => void }) {
  const refresh = useRefreshAll();
  const refreshMemory = useRefreshMemory();
  const [qty, setQty] = useState(decision.final_quantity ?? decision.recommended_quantity);
  const [days, setDays] = useState(decision.planning_lead_days);
  const [stockout, setStockout] = useState(false);
  const [notes, setNotes] = useState("");
  useEffect(() => {
    if (open) {
      setQty(decision.final_quantity ?? decision.recommended_quantity);
      setDays(decision.planning_lead_days);
      setStockout(false);
      setNotes("");
    }
  }, [open, decision]);

  const mutation = useMutation({
    mutationFn: () => api.outcome(decision.id, { delivered_quantity: qty, delivery_days: days, stockout_occurred: stockout, notes: notes || undefined }),
    onSuccess: (d) => {
      if (d.retain_error) {
        toast.warning("Outcome recorded, but not yet in operational memory", {
          description: `${d.retain_error} Use "Retry retain" on the decision.`,
        });
      } else {
        toast.success("Experience added to operational memory", {
          description: `${d.medicine_name}: ${d.outcome?.result} outcome retained in Hindsight.`,
        });
      }
      refresh();
      refreshMemory();
      onClose();
    },
    onError: (e: Error) => toast.error("Outcome could not be recorded", { description: e.message }),
  });

  return (
    <Modal
      open={open}
      onClose={() => !mutation.isPending && onClose()}
      title="Record delivery outcome"
      subtitle={`${decision.medicine_name} · ${decision.final_supplier_name} · ${decision.order_id}`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>Cancel</Button>
          <Button variant="memory" loading={mutation.isPending} onClick={() => mutation.mutate()} disabled={days <= 0 || qty < 0}>
            {mutation.isPending ? "Retaining in Hindsight…" : "Record outcome & retain"}
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-2 gap-3">
        <Field label={`Units delivered by ${decision.final_supplier_name}`}>
          <input type="number" min={0} className={inputClass} value={qty} onChange={(e) => setQty(Number(e.target.value))} />
        </Field>
        <Field label="Delivery time (days)" hint="From order to goods received">
          <input type="number" min={0.5} step={0.5} className={inputClass} value={days} onChange={(e) => setDays(Number(e.target.value))} />
        </Field>
        <div className="col-span-2">
          <span className="mb-1 block text-[12.5px] font-medium text-ink-2">Stock-out before delivery?</span>
          <div className="inline-flex rounded-md border border-line-strong p-0.5">
            {[false, true].map((v) => (
              <button
                key={String(v)}
                onClick={() => setStockout(v)}
                className={clsx(
                  "h-7 rounded-[5px] px-3 text-[12.5px] font-medium",
                  stockout === v ? (v ? "bg-crit-600 text-white" : "bg-ok-600 text-white") : "text-ink-2 hover:bg-canvas",
                )}
              >
                {v ? "Stock-out occurred" : "Stock-out avoided"}
              </button>
            ))}
          </div>
        </div>
        <div className="col-span-2">
          <Field label="Notes (optional)">
            <input className={inputClass} placeholder="e.g. Delivered in two cartons, batch B25811" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </Field>
        </div>
      </div>
      <div className="mt-4 rounded-lg border border-memory-200 bg-memory-50/60 px-3 py-2.5 text-[12.5px] text-memory-700">
        The outcome updates stock and supplier records, then a distilled experience (situation, decision, reason, delivery
        performance, outcome and lesson) is retained in Hindsight for future decisions.
      </div>
    </Modal>
  );
}
