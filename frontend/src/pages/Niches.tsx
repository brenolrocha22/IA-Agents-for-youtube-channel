import { Fragment, useState } from "react";
import { ChevronDown, ChevronRight, Play } from "lucide-react";
import { fmtDate, fmtNum, post, useApi, type Source } from "../api";
import { Async, Badge, Bar, Button, Card, Empty, EvidenceBadge, Notice, PageHeader } from "../components/ui";

interface Criterion { key: string; label: string; score: number | null; weight: number; evidence: string; rationale: string }
interface Risk { code: string; label: string; severity: string }
interface NicheScore {
  niche_id: string; name: string; market: string; total: number | null; coverage: number; confidence: string;
  recommended: boolean; blocked_reason: string | null; criteria: Criterion[]; risks: Risk[];
  opportunities: string[]; competitors: string[]; metrics: Record<string, unknown>;
}
interface Report {
  id: string; created_at: string; markets: string[]; weights: Record<string, number>; methodology: string;
  rankings: Record<string, NicheScore[]>; sources: Source[]; limitations: string[]; next_tests: string[]; report_path: string | null;
}

const SEV: Record<string, "red" | "yellow" | "gray"> = { critical: "red", high: "red", medium: "yellow", low: "gray" };

export default function Niches() {
  const q = useApi<Report | null>("/niches/latest", 8000);
  const [market, setMarket] = useState("pt");
  const [open, setOpen] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function run() {
    try {
      await post("/niches/research", { markets: ["pt", "en"], days: 7 });
      setMsg("Pesquisa iniciada (nichos + tendências). Acompanhe em Agent Control; o ranking aparece aqui ao concluir.");
    } catch (e) {
      setMsg(`Erro: ${e instanceof Error ? e.message : e}`);
    }
  }

  return (
    <>
      <PageHeader title="Niche Intelligence" subtitle="Ranking explicável 0–100. Fatos, estimativas e hipóteses são sempre identificados."
        actions={<Button onClick={run}><Play className="h-4 w-4" /> Executar pesquisa</Button>} />
      {msg && <div className="mb-4"><Notice>{msg}</Notice></div>}
      <Async q={q}>
        {(r) => !r ? <Empty>Nenhum relatório ainda. Clique em “Executar pesquisa”.</Empty> : (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
              <span>Coleta: <b className="text-white">{fmtDate(r.created_at)}</b></span>
              {r.report_path && <span>Relatório: <code className="text-zinc-300">{r.report_path}</code></span>}
              <div className="ml-auto flex gap-1" role="tablist">
                {r.markets.map((m) => (
                  <button key={m} role="tab" aria-selected={market === m} onClick={() => setMarket(m)}
                    className={`rounded-lg px-3 py-1.5 ${market === m ? "bg-accent text-white" : "border border-line"}`}>
                    {m === "pt" ? "Brasil (pt)" : "Inglês (en)"}
                  </button>
                ))}
              </div>
            </div>

            <Card title={`Ranking — ${market === "pt" ? "mercado primário pt-BR" : "comparação en"}`}>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-left text-xs uppercase text-muted">
                    <tr><th className="py-2">#</th><th>Nicho</th><th className="w-40">Nota</th><th>Cobertura</th><th>Confiança</th><th>Situação</th></tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {(r.rankings[market] ?? []).map((n, i) => (
                      <Fragment key={n.niche_id}>
                        <tr className="cursor-pointer hover:bg-panel-2" onClick={() => setOpen(open === n.niche_id ? null : n.niche_id)}>
                          <td className="py-2">{i + 1}</td>
                          <td className="flex items-center gap-1 py-2">{open === n.niche_id ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}{n.name}</td>
                          <td><div className="flex items-center gap-2"><span className="w-10 font-semibold">{n.total ?? "?"}</span><Bar value={n.total} color="bg-brand" /></div></td>
                          <td>{Math.round(n.coverage * 100)}%</td>
                          <td>{n.confidence}</td>
                          <td>{n.blocked_reason ? <Badge color="red">bloqueado</Badge> : n.recommended ? <Badge color="green">recomendado</Badge> : <Badge>em observação</Badge>}</td>
                        </tr>
                        {open === n.niche_id && (
                          <tr><td colSpan={6} className="bg-panel-2/50 p-4">
                            {n.blocked_reason && <div className="mb-3"><Notice kind="error">{n.blocked_reason}</Notice></div>}
                            <div className="grid gap-4 lg:grid-cols-2">
                              <div className="space-y-3">
                                <h3 className="text-xs font-semibold uppercase text-muted">Critérios e evidências</h3>
                                {n.criteria.map((c) => (
                                  <div key={c.key}>
                                    <div className="flex items-center justify-between gap-2 text-sm">
                                      <span>{c.label} <span className="text-xs text-muted">(peso {Math.round(c.weight * 100)}%)</span></span>
                                      <span className="flex items-center gap-2">{c.score ?? "desconhecido"} <EvidenceBadge e={c.evidence} /></span>
                                    </div>
                                    <Bar value={c.score} />
                                    <p className="mt-1 text-xs text-muted">{c.rationale}</p>
                                  </div>
                                ))}
                              </div>
                              <div className="space-y-4 text-sm">
                                <div><h3 className="mb-1 text-xs font-semibold uppercase text-muted">Riscos</h3>
                                  <ul className="space-y-1">{n.risks.map((x) => <li key={x.code} className="flex gap-2"><Badge color={SEV[x.severity]}>{x.severity}</Badge>{x.label}</li>)}</ul></div>
                                <div><h3 className="mb-1 text-xs font-semibold uppercase text-muted">Oportunidades</h3>
                                  <ul className="list-disc pl-5">{n.opportunities.map((o) => <li key={o}>{o}</li>)}</ul></div>
                                <div><h3 className="mb-1 text-xs font-semibold uppercase text-muted">Concorrentes (vídeos públicos recentes)</h3>
                                  {n.competitors.length ? n.competitors.join(", ") : <span className="text-muted">Indisponível — configure YOUTUBE_API_KEY.</span>}</div>
                                <div><h3 className="mb-1 text-xs font-semibold uppercase text-muted">Dados observados</h3>
                                  <p>Média diária por artigo: {fmtNum(n.metrics.avg_daily_views as number)} · Crescimento: {String(n.metrics.growth_ratio ?? "—")} · Período: {String(n.metrics.period ?? "—")}</p>
                                  {(n.metrics.seeds_missing as string[] | undefined)?.length ? <p className="text-xs text-amber-300">Artigos não encontrados: {(n.metrics.seeds_missing as string[]).join(", ")}</p> : null}</div>
                              </div>
                            </div>
                          </td></tr>
                        )}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <div className="grid gap-6 lg:grid-cols-2">
              <Card title="Metodologia e pesos">
                <p className="text-sm text-zinc-300">{r.methodology}</p>
                <ul className="mt-3 grid grid-cols-2 gap-1 text-sm">{Object.entries(r.weights).map(([k, v]) => <li key={k}>{k}: <b>{Math.round(v * 100)}%</b></li>)}</ul>
                <p className="mt-2 text-xs text-muted">Pesos editáveis em config/scoring.json.</p>
              </Card>
              <Card title="Limitações e próximos testes">
                <ul className="list-disc space-y-1 pl-5 text-sm text-zinc-300">{r.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
                <h3 className="mb-1 mt-4 text-xs font-semibold uppercase text-muted">Próximos testes</h3>
                <ul className="list-disc space-y-1 pl-5 text-sm text-zinc-300">{r.next_tests.map((l) => <li key={l}>{l}</li>)}</ul>
              </Card>
            </div>

            <Card title={`Fontes (${r.sources.length})`}>
              <ul className="max-h-72 space-y-1 overflow-y-auto text-sm">
                {r.sources.map((s) => (
                  <li key={s.id} className="flex flex-wrap gap-2"><EvidenceBadge e={s.evidence} />
                    <a className="text-accent hover:underline" href={s.url} target="_blank" rel="noreferrer">{s.title}</a>
                    <span className="text-xs text-muted">coletado em {fmtDate(s.collected_at)}</span></li>
                ))}
              </ul>
            </Card>
          </div>
        )}
      </Async>
    </>
  );
}
