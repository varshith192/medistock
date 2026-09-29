import { clsx } from "clsx";
import { AlertTriangle, Loader2, X } from "lucide-react";
import { useEffect, useRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import type { RiskLevel } from "../lib/types";

/* ── Button ─────────────────────────────────────────────────────────────── */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "memory";

export function Button({
  variant = "secondary",
  size = "md",
  loading,
  icon,
  className,
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "sm" | "md";
  loading?: boolean;
  icon?: ReactNode;
}) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 rounded-md font-medium whitespace-nowrap transition-colors",
        "disabled:opacity-55",
        size === "sm" ? "h-7 px-2.5 text-[12.5px]" : "h-9 px-3.5 text-[13px]",
        variant === "primary" && "bg-brand-700 text-white hover:bg-brand-600 shadow-xs",
        variant === "secondary" && "border border-line-strong bg-surface text-ink-2 hover:bg-canvas shadow-xs",
        variant === "ghost" && "text-ink-2 hover:bg-black/[0.04]",
        variant === "danger" && "border border-crit-200 bg-surface text-crit-700 hover:bg-crit-50",
        variant === "memory" && "bg-memory-600 text-white hover:bg-memory-700 shadow-xs",
        className,
      )}
    >
      {loading ? <Loader2 className="size-3.5 animate-spin" /> : icon}
      {children}
    </button>
  );
}

/* ── Surfaces ───────────────────────────────────────────────────────────── */

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={clsx("rounded-lg border border-line bg-surface", className)}>{children}</div>;
}

export function CardHeader({
  title,
  subtitle,
  action,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("flex items-start justify-between gap-4 border-b border-line px-4 py-3", className)}>
      <div className="min-w-0">
        <h3 className="text-[13.5px] font-semibold text-ink">{title}</h3>
        {subtitle && <p className="mt-0.5 text-[12.5px] text-muted">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-[22px] font-semibold tracking-[-0.01em] text-ink">{title}</h1>
        {subtitle && <p className="mt-1 text-[13.5px] text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

/* ── Badges ─────────────────────────────────────────────────────────────── */

export type Tone = "neutral" | "brand" | "memory" | "crit" | "high" | "med" | "ok";

const toneClass: Record<Tone, string> = {
  neutral: "bg-canvas text-ink-2 ring-line-strong",
  brand: "bg-brand-50 text-brand-700 ring-brand-200",
  memory: "bg-memory-50 text-memory-700 ring-memory-200",
  crit: "bg-crit-50 text-crit-700 ring-crit-200",
  high: "bg-high-50 text-high-700 ring-high-200",
  med: "bg-med-50 text-med-700 ring-med-200",
  ok: "bg-ok-50 text-ok-700 ring-ok-200",
};

export function Badge({
  tone = "neutral",
  children,
  className,
  dot,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
  dot?: boolean;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-[5px] px-1.5 py-0.5 text-[11.5px] font-medium ring-1 ring-inset whitespace-nowrap",
        toneClass[tone],
        className,
      )}
    >
      {dot && <span className="size-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

export const riskTone = (level: RiskLevel | string): Tone =>
  ({ CRITICAL: "crit", HIGH: "high", MEDIUM: "med", LOW: "ok" })[level.toUpperCase()] as Tone ?? "neutral";

export function RiskBadge({ level }: { level: RiskLevel }) {
  return (
    <Badge tone={riskTone(level)} dot>
      {level}
    </Badge>
  );
}


/* ── Feedback states ────────────────────────────────────────────────────── */

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("skeleton", className)} />;
}

export function SkeletonRows({ rows = 6, className }: { rows?: number; className?: string }) {
  return (
    <div className={clsx("space-y-2.5 p-4", className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("flex flex-col items-center justify-center px-6 py-12 text-center", className)}>
      {icon && <div className="mb-3 grid size-10 place-items-center rounded-lg bg-canvas text-muted">{icon}</div>}
      <p className="text-[13.5px] font-medium text-ink">{title}</p>
      {description && <p className="mt-1 max-w-md text-[12.5px] text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="flex items-start gap-3 rounded-lg border border-crit-200 bg-crit-50 px-4 py-3">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-crit-600" />
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-medium text-crit-700">Something went wrong</p>
        <p className="mt-0.5 text-[12.5px] break-words text-crit-700/90">{message}</p>
      </div>
      {onRetry && (
        <Button size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

/* ── Overlays ───────────────────────────────────────────────────────────── */

function useEscape(open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);
}

export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  actions,
  children,
  width = "max-w-[860px]",
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  width?: string;
}) {
  useEscape(open, onClose);
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (open) panel.current?.focus();
  }, [open]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-ink/25" onClick={onClose} />
      <div
        ref={panel}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        className={clsx("animate-slide-in relative flex h-full w-full flex-col bg-canvas shadow-2xl outline-none", width)}
      >
        <div className="flex items-start justify-between gap-4 border-b border-line bg-surface px-6 py-4">
          <div className="min-w-0">
            <div className="text-[17px] font-semibold text-ink">{title}</div>
            {subtitle && <div className="mt-0.5 text-[12.5px] text-muted">{subtitle}</div>}
          </div>
          <div className="flex items-center gap-2">
            {actions}
            <button onClick={onClose} className="rounded-md p-1.5 text-muted hover:bg-canvas" aria-label="Close">
              <X className="size-4" />
            </button>
          </div>
        </div>
        <div className="thin-scroll flex-1 overflow-y-auto px-6 py-5">{children}</div>
      </div>
    </div>
  );
}

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  width = "max-w-lg",
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}) {
  useEscape(open, onClose);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-ink/30" onClick={onClose} />
      <div role="dialog" aria-modal="true" className={clsx("animate-fade-in relative w-full rounded-xl bg-surface shadow-2xl", width)}>
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div>
            <div className="text-[15px] font-semibold text-ink">{title}</div>
            {subtitle && <div className="mt-0.5 text-[12.5px] text-muted">{subtitle}</div>}
          </div>
          <button onClick={onClose} className="rounded-md p-1 text-muted hover:bg-canvas" aria-label="Close">
            <X className="size-4" />
          </button>
        </div>
        <div className="thin-scroll max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-line bg-canvas/60 px-5 py-3 rounded-b-xl">{footer}</div>}
      </div>
    </div>
  );
}

/* ── Form controls ──────────────────────────────────────────────────────── */

export function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[12.5px] font-medium text-ink-2">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[11.5px] text-muted">{hint}</span>}
    </label>
  );
}

/** Input styling without a width, for controls sized by the caller. */
export const inputBase =
  "h-9 rounded-md border border-line-strong bg-surface px-3 text-[13px] text-ink placeholder:text-faint focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100";
export const inputClass = `${inputBase} w-full`;

/* ── Misc ───────────────────────────────────────────────────────────────── */

export function SegmentedControl<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: ReactNode; count?: number }[];
}) {
  return (
    <div className="inline-flex rounded-md border border-line-strong bg-surface p-0.5">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={clsx(
            "flex h-7 items-center gap-1.5 rounded-[5px] px-2.5 text-[12.5px] font-medium transition-colors",
            value === opt.value ? "bg-ink text-white" : "text-ink-2 hover:bg-canvas",
          )}
        >
          {opt.label}
          {opt.count !== undefined && (
            <span className={clsx("tabular text-[11px]", value === opt.value ? "text-white/70" : "text-faint")}>{opt.count}</span>
          )}
        </button>
      ))}
    </div>
  );
}
