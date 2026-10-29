import { useCallback, useEffect, useRef, useState } from "react";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: init?.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* resposta sem JSON */
    }
    throw new ApiError(res.status, detail || `Erro ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const post = <T,>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body instanceof FormData ? body : JSON.stringify(body ?? {}) });
export const put = <T,>(path: string, body: unknown) => api<T>(path, { method: "PUT", body: JSON.stringify(body) });

/** Carrega dados com estados de carregamento/erro e, opcionalmente, atualização periódica. */
export function useApi<T>(path: string | null, pollMs?: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const first = useRef(true);

  const load = useCallback(async () => {
    if (!path) return;
    if (first.current) setLoading(true);
    try {
      setData(await api<T>(path));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
      first.current = false;
    }
  }, [path]);

  useEffect(() => {
    first.current = true;
    load();
    if (!pollMs) return;
    const id = setInterval(load, pollMs);
    return () => clearInterval(id);
  }, [load, pollMs]);

  return { data, error, loading, reload: load };
}

export const mediaUrl = (path: string) => `/media/${path.replace(/^output\//, "")}`;

export const fmtDate = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—";

export const fmtNum = (n?: number | null, digits = 0) =>
  n === null || n === undefined ? "—" : n.toLocaleString("pt-BR", { maximumFractionDigits: digits });

// ---- Tipos usados em várias páginas ----
export type TaskStatus = "pending" | "running" | "completed" | "failed" | "cancelled" | "awaiting_approval";

export interface Task {
  id: string;
  type: string;
  agent: string;
  status: TaskStatus;
  workflow_id: string | null;
  depends_on: string[];
  attempts: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  result: { ok: boolean; summary: string; output: Record<string, unknown>; tokens_estimated: number; cost_estimated_usd: number } | null;
  errors: string[];
  requires_approval: boolean;
  decided_by: string | null;
}

export interface Workflow {
  id: string;
  kind: string;
  title: string;
  status: TaskStatus;
  created_at: string;
  finished_at: string | null;
  task_ids: string[];
  api_calls: number;
  cost_estimated_usd: number;
  tokens_estimated: number;
  params: Record<string, unknown>;
}

export interface QualityCheck {
  code: string;
  label: string;
  status: "pass" | "warn" | "fail";
  detail: string;
  field: string | null;
}

export interface QualityReport {
  id: string;
  created_at: string;
  target_kind: string;
  target_id: string;
  checks: QualityCheck[];
  blocking: boolean;
  disclaimer: string;
}

export interface Source {
  id: string;
  provider: string;
  title: string;
  url: string;
  collected_at: string;
  evidence: string;
  license: string | null;
  note: string | null;
}

export interface Section {
  kind: string;
  heading: string;
  narration: string;
  visual_note: string;
  on_screen_text: string;
  source_ids: string[];
  est_seconds: number;
}

export interface Script {
  id: string;
  brief_id: string;
  created_at: string;
  format: string;
  language: string;
  tone: string;
  title: string;
  title_variants: string[];
  description: string;
  hashtags: string[];
  thumbnail_ideas: string[];
  sections: Section[];
  sources: Source[];
  loop: boolean;
  retention_notes: string[];
  status: "draft" | "approved" | "rejected";
  provider: string;
  edited_by_human: boolean;
  est_duration_s: number;
  planned_date: string | null;
  channel_id: string | null;
  story_id: string | null;
  visual_plan_id: string | null;
  rights_notes: string[];
}

export interface Job {
  id: string;
  script_id: string;
  orientation: string;
  status: string;
  stage: string;
  progress: number;
  created_at: string;
  outputs: Record<string, string>;
  rights_manifest: Record<string, string>[];
  log: string[];
  media: Record<string, unknown>;
}
