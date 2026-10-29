import { useState } from "react";
import { Link } from "react-router-dom";
import { fmtDate, fmtNum, useApi, type Source } from "../api";
import { Async, Badge, Card, Empty, PageHeader, inputCls } from "../components/ui";

interface Item { title: string; lang: string; url: string; views: number; days_present: number; best_rank: number; category: string; description: string | null; emerging: boolean; sensitive: boolean }
interface TrendsData { run: { id: string; collected_at: string; window: string[]; source: Source } | null; items: Item[]; categories: string[] }
interface Run { id: string; lang: string; collected_at: string; items: number; window: string[] }

export default function Trends() {
  const [lang, setLang] = useState("pt");
  const [category, setCategory] = useState("");
  const [emerging, setEmerging] = useState(false);
  const [runId, setRunId] = useState("");
  const params = new URLSearchParams({ lang, emerging: String(emerging), ...(category && { category }), ...(runId && { run_id: runId }) });
  const q = useApi<TrendsData>(`/trends?${params}`);
  const runs = useApi<Run[]>("/trends/runs");

  return (
    <>
      <PageHeader title="Trend Explorer" subtitle="Assuntos mais acessados na Wikipedia por idioma (proxy de interesse público, não de buscas no YouTube)." />
      <div className="mb-4 flex flex-wrap gap-3">
        <select aria-label="Idioma" className={`${inputCls} w-auto`} value={lang} onChange={(e) => { setLang(e.target.value); setRunId(""); setCategory(""); }}>
          <option value="pt">Português</option><option value="en">Inglês</option>
        </select>
        <select aria-label="Categoria" className={`${inputCls} w-auto`} value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">Todas as categorias</option>
          {q.data?.categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={emerging} onChange={(e) => setEmerging(e.target.checked)} /> Somente emergentes</label>
      </div>
      <div className="grid gap-6 lg:grid-cols-4">
        <div className="lg:col-span-3">
          <Async q={q}>
            {(d) => !d.run ? <Empty>Nenhuma coleta para este idioma. Execute a pesquisa em Niche Intelligence.</Empty> : (
              <Card title={`Coleta de ${fmtDate(d.run.collected_at)} · janela ${d.run.window[0]} a ${d.run.window.at(-1)}`}>
                {d.items.length === 0 ? <Empty>Nenhum assunto com estes filtros.</Empty> : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="text-left text-xs uppercase text-muted"><tr><th className="py-2">Assunto</th><th>Categoria</th><th>Visualizações</th><th>Dias</th><th></th></tr></thead>
                      <tbody className="divide-y divide-line">
                        {d.items.map((i) => (
                          <tr key={i.title}>
                            <td className="py-2">
                              <a href={i.url} target="_blank" rel="noreferrer" className="font-medium hover:underline">{i.title}</a>
                              <div className="text-xs text-muted">{i.description}</div>
                              <div className="mt-1 flex gap-1">{i.emerging && <Badge color="blue">emergente</Badge>}{i.sensitive && <Badge color="yellow">sensível</Badge>}</div>
                            </td>
                            <td><Badge>{i.category}</Badge></td>
                            <td>{fmtNum(i.views)}</td>
                            <td>{i.days_present}/{d.run!.window.length}</td>
                            <td>{!i.sensitive && <Link className="text-xs text-accent hover:underline" to={`/studio?topic=${encodeURIComponent(i.title)}`}>Criar Short</Link>}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                <p className="mt-3 text-xs text-muted">Fonte: {d.run.source.title} — {d.run.source.note}</p>
              </Card>
            )}
          </Async>
        </div>
        <Card title="Histórico de coletas">
          <Async q={runs}>
            {(rs) => rs.length === 0 ? <Empty>Sem histórico.</Empty> : (
              <ul className="space-y-1 text-sm">
                {rs.map((r) => (
                  <li key={r.id}><button onClick={() => { setLang(r.lang); setRunId(r.id); }} className={`w-full rounded-lg px-2 py-1 text-left hover:bg-panel-2 ${runId === r.id ? "bg-panel-2" : ""}`}>
                    {fmtDate(r.collected_at)} · {r.lang} · {r.items} itens</button></li>
                ))}
              </ul>
            )}
          </Async>
        </Card>
      </div>
    </>
  );
}
