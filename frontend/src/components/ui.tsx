import type { ReactNode } from "react";
import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import type { TaskStatus } from "../api";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

export function Card({ title, children, className = "", actions }: { title?: string; children: ReactNode; className?: string; actions?: ReactNode }) {
  return (
    <section className={`rounded-xl border border-line bg-panel p-4 ${className}`}>
      {(title || actions) && (
        <div className="mb-3 flex items-center justify-between gap-2">
          {title && <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, hint, tone = "default" }: { label: string; value: ReactNode; hint?: string; tone?: "default" | "red" | "blue" }) {
  const color = tone === "red" ? "text-brand" : tone === "blue" ? "text-accent" : "text-white";
  return (
    <div className="rounded-xl border border-line bg-panel p-4">
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${color}`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}

const BADGE: Record<string, string> = {
  green: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  red: "bg-red-500/15 text-red-300 border-red-500/30",
  blue: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  yellow: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  gray: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30",
};

export function Badge({ children, color = "gray" }: { children: ReactNode; color?: keyof typeof BADGE }) {
  return <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${BADGE[color]}`}>{children}</span>;
}

const STATUS: Record<string, [string, keyof typeof BADGE]> = {
  pending: ["pendente", "gray"],
  running: ["executando", "blue"],
  completed: ["concluída", "green"],
  failed: ["falhou", "red"],
  cancelled: ["cancelada", "gray"],
  awaiting_approval: ["aguardando aprovação", "yellow"],
  rendered: ["renderizado", "green"],
  queued: ["na fila", "gray"],
  draft: ["rascunho", "gray"],
  approved: ["aprovado", "green"],
  rejected: ["rejeitado", "red"],
  pass: ["ok", "green"],
  warn: ["alerta", "yellow"],
  fail: ["falha", "red"],
};

export function StatusBadge({ status }: { status: TaskStatus | string }) {
  const [label, color] = STATUS[status] ?? [status, "gray"];
  return <Badge color={color}>{label}</Badge>;
}

const EVIDENCE: Record<string, keyof typeof BADGE> = { observado: "green", estimativa: "blue", "hipótese": "yellow", desconhecido: "gray" };
export const EvidenceBadge = ({ e }: { e: string }) => <Badge color={EVIDENCE[e] ?? "gray"}>{e}</Badge>;

export function Button({
  children, onClick, variant = "primary", disabled, type = "button", title,
}: { children: ReactNode; onClick?: () => void; variant?: "primary" | "secondary" | "danger" | "ghost"; disabled?: boolean; type?: "button" | "submit"; title?: string }) {
  const styles = {
    primary: "bg-brand text-white hover:bg-red-500",
    secondary: "bg-accent text-white hover:bg-blue-500",
    danger: "border border-red-500/50 text-red-300 hover:bg-red-500/10",
    ghost: "border border-line text-zinc-200 hover:bg-panel-2",
  }[variant];
  return (
    <button type={type} title={title} onClick={onClick} disabled={disabled}
      className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${styles}`}>
      {children}
    </button>
  );
}

export const Loading = ({ label = "Carregando…" }: { label?: string }) => (
  <div role="status" className="flex items-center gap-2 p-6 text-sm text-muted">
    <Loader2 className="h-4 w-4 animate-spin" /> {label}
  </div>
);

export const Empty = ({ children }: { children: ReactNode }) => (
  <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-line p-6 text-center text-sm text-muted">
    <Inbox className="h-5 w-5" /> {children}
  </div>
);

export const ErrorState = ({ message, onRetry }: { message: string; onRetry?: () => void }) => (
  <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
    <AlertTriangle className="h-4 w-4" />
    <span className="flex-1">Erro: {message}</span>
    {onRetry && <Button variant="ghost" onClick={onRetry}>Tentar novamente</Button>}
  </div>
);

export function Notice({ kind = "info", children }: { kind?: "info" | "success" | "error" | "warn"; children: ReactNode }) {
  const c = { info: "border-blue-500/40 bg-blue-500/10 text-blue-100", success: "border-emerald-500/40 bg-emerald-500/10 text-emerald-100",
    error: "border-red-500/40 bg-red-500/10 text-red-100", warn: "border-amber-500/40 bg-amber-500/10 text-amber-100" }[kind];
  return <div className={`rounded-lg border p-3 text-sm ${c}`}>{children}</div>;
}

export function Bar({ value, max = 100, color = "bg-accent" }: { value: number | null; max?: number; color?: string }) {
  const pct = value === null ? 0 : Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="h-2 w-full overflow-hidden rounded bg-panel-2" aria-hidden>
      <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

/** Renderiza estados padrão de uma consulta. */
export function Async<T>({ q, empty, children }: { q: { data: T | null; error: string | null; loading: boolean; reload: () => void }; empty?: (d: T) => boolean; children: (d: T) => ReactNode }) {
  if (q.loading && !q.data) return <Loading />;
  if (q.error && !q.data) return <ErrorState message={q.error} onRetry={q.reload} />;
  if (!q.data) return <Empty>Sem dados.</Empty>;
  if (empty?.(q.data)) return null;
  return <>{children(q.data)}</>;
}

export const inputCls = "w-full rounded-lg border border-line bg-panel-2 px-3 py-2 text-sm text-white placeholder:text-zinc-500 focus:border-accent focus:outline-none";
