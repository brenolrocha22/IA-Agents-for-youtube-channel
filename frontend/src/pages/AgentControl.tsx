import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fmtDate, fmtNum, useApi, type Task, type TaskStatus } from "../api";
import { Async, Bar, Card, Empty, PageHeader, StatusBadge, inputCls } from "../components/ui";

interface AgentInfo {
  name: string; title: string; description: string; task_types: string[]; counts: Record<TaskStatus, number>;
  last_activity: string | null; last_error: string | null; tokens_estimated: number; cost_estimated_usd: number;
}

export default function AgentControl() {
  const agents = useApi<AgentInfo[]>("/agents", 5000);
  const [params] = useSearchParams();
  const [status, setStatus] = useState(params.get("status") ?? "");
  const tasks = useApi<Task[]>(`/tasks?limit=60${status ? `&status=${status}` : ""}`, 4000);
  const logs = useApi<{ ts: string; level: string; source: string; message: string }[]>("/logs?limit=40", 4000);
  const plans = useApi<{ id: string; script_id: string; updated_at: string; subject: string; providers: string[]; scenes: number; validated: number;
    review: number; pending: number; found: number; downloaded: number; licenses: string[]; coverage: number }[]>("/visual/plans", 8000);
  return (
    <>
      <PageHeader title="Agent Control" subtitle="Agentes sob demanda com contratos tipados. Limites e política são somente leitura." />
      <div className="space-y-6">
        <Async q={agents}>
          {(list) => (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {list.map((a) => (
                <Card key={a.name}>
                  <div className="font-semibold">{a.title}</div>
                  <p className="mt-1 text-xs text-muted">{a.description}</p>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <span>✔ {a.counts.completed}</span><span className="text-blue-300">▶ {a.counts.running}</span>
                    <span className="text-amber-300">⏸ {a.counts.awaiting_approval}</span><span className="text-red-300">✖ {a.counts.failed}</span>
                  </div>
                  <div className="mt-2 text-xs text-muted">Última atividade: {fmtDate(a.last_activity)} · Tokens: {fmtNum(a.tokens_estimated)} · US$ {a.cost_estimated_usd.toFixed(2)}</div>
                  {a.last_error && <p className="mt-2 break-words rounded bg-red-500/10 p-2 text-xs text-red-200">{a.last_error}</p>}
                </Card>
              ))}
            </div>
          )}
        </Async>
        <Card title="Visual Hunter — planos visuais">
          <Async q={plans}>
            {(ps) => ps.length === 0 ? <Empty>Nenhum roteiro analisado ainda.</Empty> : (
              <div className="overflow-x-auto"><table className="w-full text-sm">
                <thead className="text-left text-xs uppercase text-muted"><tr><th className="py-2">Roteiro / assunto</th><th>Cenas</th><th>Validadas</th>
                  <th>Em revisão</th><th>Pendentes</th><th>Encontrados</th><th>Baixados</th><th>Licenças</th><th className="w-40">Cobertura</th></tr></thead>
                <tbody className="divide-y divide-line">{ps.map((p) => (
                  <tr key={p.id}><td className="py-2">{p.subject}<div className="text-xs text-muted">{p.script_id} · {fmtDate(p.updated_at)} · {p.providers.join(", ")}</div></td>
                    <td>{p.scenes}</td><td className="text-emerald-300">{p.validated}</td><td className="text-amber-300">{p.review}</td>
                    <td className="text-red-300">{p.pending}</td><td>{p.found}</td><td>{p.downloaded}</td>
                    <td className="text-xs">{p.licenses.join(", ")}</td>
                    <td><div className="flex items-center gap-2"><span className="w-10">{Math.round(p.coverage * 100)}%</span><Bar value={p.coverage * 100} color={p.coverage >= 0.999 ? "bg-emerald-500" : "bg-brand"} /></div></td></tr>
                ))}</tbody>
              </table></div>
            )}
          </Async>
        </Card>
        <div className="grid gap-6 lg:grid-cols-3">
          <Card title="Tarefas" className="lg:col-span-2" actions={
            <select aria-label="Filtrar estado" className={`${inputCls} w-auto py-1`} value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">Todos</option>{["pending", "running", "awaiting_approval", "completed", "failed", "cancelled"].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>}>
            <Async q={tasks}>
              {(ts) => ts.length === 0 ? <Empty>Nenhuma tarefa.</Empty> : (
                <div className="overflow-x-auto"><table className="w-full text-sm">
                  <thead className="text-left text-xs uppercase text-muted"><tr><th className="py-2">Tipo</th><th>Agente</th><th>Estado</th><th>Tent.</th><th>Criada</th><th>Resultado</th></tr></thead>
                  <tbody className="divide-y divide-line">{ts.map((t) => (
                    <tr key={t.id}><td className="py-2">{t.type}</td><td>{t.agent}</td><td><StatusBadge status={t.status} /></td><td>{t.attempts}</td>
                      <td className="text-xs text-muted">{fmtDate(t.created_at)}</td><td className="max-w-xs truncate text-xs" title={t.errors.at(-1) ?? t.result?.summary}>{t.errors.at(-1) ?? t.result?.summary ?? ""}</td></tr>
                  ))}</tbody>
                </table></div>
              )}
            </Async>
          </Card>
          <Card title="Logs">
            <Async q={logs}>
              {(ls) => ls.length === 0 ? <Empty>Sem logs.</Empty> : (
                <ul className="max-h-[480px] space-y-1 overflow-y-auto font-mono text-xs">
                  {ls.map((l, i) => <li key={i} className={l.level === "error" ? "text-red-300" : l.level === "warning" ? "text-amber-300" : "text-zinc-300"}>[{fmtDate(l.ts)}] {l.source}: {l.message}</li>)}
                </ul>
              )}
            </Async>
          </Card>
        </div>
      </div>
    </>
  );
}
