import { Link } from "react-router-dom";
import { ChefHat, Sparkles } from "lucide-react";
import { fmtDate, fmtNum, useApi, type TaskStatus } from "../api";
import Approvals from "../components/Approvals";
import { Async, Badge, Bar, Card, Empty, PageHeader, Stat, StatusBadge } from "../components/ui";

interface DashboardData {
  projects: { id: string; title: string; kind: string; status: TaskStatus; created_at: string }[];
  project_count: number;
  tasks_by_status: Record<TaskStatus, number>;
  active_tasks: { id: string; type: string; agent: string; status: TaskStatus }[];
  videos_rendered: number;
  videos_failed: number;
  errors: { ts: string; source: string; message: string }[];
  cost_estimated_usd: number;
  tokens_estimated: number;
  api_calls: number;
  top_niches: { name: string; total: number | null; recommended: boolean; confidence: string }[];
  niche_report_date: string | null;
  opportunities: { title: string; category: string; views: number; url: string; description: string | null }[];
  trend_date: string | null;
}

interface KitchenOverview {
  counts: Record<string, number>;
}

export default function Dashboard() {
  const q = useApi<DashboardData>("/dashboard", 5000);
  const kq = useApi<KitchenOverview>("/kitchen/overview", 10000);
  return (
    <>
      <PageHeader title="Dashboard" subtitle="Visão geral de projetos, produção e oportunidades."
        actions={<Link to="/studio" className="rounded-lg bg-brand px-3 py-2 text-sm font-medium hover:bg-red-500">Novo Short</Link>} />
      <Async q={q}>
        {(d) => (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
              <Stat label="Projetos" value={d.project_count} />
              {(() => {
                // Pendência que depende do proprietário tem prioridade: leva direto à revisão daquela tarefa.
                const awaiting = d.active_tasks.find((t) => t.status === "awaiting_approval");
                const running = d.active_tasks.find((t) => t.status === "running");
                const to = awaiting ? `/factory?task=${awaiting.id}` : running ? "/agentes?status=running" : undefined;
                return (
                  <Stat label="Tarefas em andamento" value={(d.tasks_by_status.running ?? 0) + (d.tasks_by_status.awaiting_approval ?? 0)}
                    hint={`${d.tasks_by_status.awaiting_approval ?? 0} aguardando aprovação`} tone="blue" to={to}
                    action={awaiting ? (awaiting.type === "final_approval" ? "Assistir e aprovar vídeo" : "Revisar roteiro") : running ? "Ver execução" : undefined} />
                );
              })()}
              <Stat label="Vídeos produzidos" value={d.videos_rendered} hint={d.videos_failed ? `${d.videos_failed} com falha` : undefined}
                to={d.videos_rendered ? "/videos" : undefined} action={d.videos_rendered ? "Ver vídeos e resultados" : undefined} />
              <Stat label="Erros recentes" value={d.errors.length} tone={d.errors.length ? "red" : "default"} />
              <Stat label="Custo estimado" value={`US$ ${d.cost_estimated_usd.toFixed(2)}`} hint={`${fmtNum(d.api_calls)} chamadas de API · ${fmtNum(d.tokens_estimated)} tokens`} />
            </div>

            <div className="grid gap-6 lg:grid-cols-3">
              <Card title="Aprovações necessárias" className="lg:col-span-2"><Approvals onChange={q.reload} /></Card>
              <Card title="Reality Kitchen Stories" actions={<Link to="/kitchen" className="text-xs text-accent">abrir</Link>}>
                {kq.data ? (
                  <dl className="grid grid-cols-2 gap-3 text-sm">
                    {Object.entries({ episodes: "Episódios pesquisados", restaurants: "Restaurantes", stories: "Histórias", pending_verification: "Fatos a verificar", scripts: "Roteiros", videos_done: "Vídeos concluídos" })
                      .map(([k, label]) => (
                        <div key={k}><dt className="text-xs text-muted">{label}</dt><dd className="text-lg font-semibold">{kq.data!.counts[k] ?? 0}</dd></div>
                      ))}
                  </dl>
                ) : <div className="flex items-center gap-2 text-sm text-muted"><ChefHat className="h-4 w-4" /> {kq.error ?? "Carregando…"}</div>}
              </Card>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <Card title="Top nichos (pt-BR)" actions={<span className="text-xs text-muted">{fmtDate(d.niche_report_date)}</span>}>
                {d.top_niches.length === 0 ? <Empty>Nenhuma pesquisa executada. <Link className="text-accent" to="/nichos">Executar pesquisa</Link></Empty> : (
                  <ul className="space-y-3">
                    {d.top_niches.map((n) => (
                      <li key={n.name}>
                        <div className="mb-1 flex items-center justify-between text-sm">
                          <span>{n.name} {n.recommended && <Badge color="green">recomendado</Badge>}</span>
                          <span className="text-muted">{n.total ?? "?"} · confiança {n.confidence}</span>
                        </div>
                        <Bar value={n.total} color="bg-brand" />
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
              <Card title="Últimas oportunidades (assuntos emergentes)" actions={<span className="text-xs text-muted">{fmtDate(d.trend_date)}</span>}>
                {d.opportunities.length === 0 ? <Empty>Sem coleta de tendências. <Link className="text-accent" to="/tendencias">Ver Trend Explorer</Link></Empty> : (
                  <ul className="divide-y divide-line">
                    {d.opportunities.map((o) => (
                      <li key={o.title} className="flex items-center gap-3 py-2 text-sm">
                        <Sparkles className="h-4 w-4 shrink-0 text-accent" />
                        <a href={o.url} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate hover:underline">{o.title}</a>
                        <Badge>{o.category}</Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <Card title="Projetos recentes">
                {d.projects.length === 0 ? <Empty>Nenhum projeto ainda.</Empty> : (
                  <ul className="divide-y divide-line">
                    {d.projects.map((p) => (
                      <li key={p.id} className="flex items-center gap-3 py-2 text-sm">
                        <span className="min-w-0 flex-1 truncate">{p.title}</span>
                        <span className="text-xs text-muted">{fmtDate(p.created_at)}</span>
                        <StatusBadge status={p.status} />
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
              <Card title="Erros recentes">
                {d.errors.length === 0 ? <Empty>Nenhum erro registrado.</Empty> : (
                  <ul className="space-y-2 text-sm">
                    {d.errors.map((e, i) => (
                      <li key={i} className="rounded-lg bg-red-500/10 p-2"><span className="text-xs text-muted">{fmtDate(e.ts)} · {e.source}</span><div className="break-words text-red-200">{e.message}</div></li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>
          </div>
        )}
      </Async>
    </>
  );
}
