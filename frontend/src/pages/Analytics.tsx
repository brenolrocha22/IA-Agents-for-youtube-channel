import { useState, type ChangeEvent } from "react";
import { Upload } from "lucide-react";
import { fmtDate, fmtNum, post, useApi } from "../api";
import { Async, Bar, Button, Card, Empty, Notice, PageHeader, Stat, inputCls } from "../components/ui";

interface Group { group: string; n: number; views_avg: number | null; ctr_avg: number | null; avg_view_pct: number | null; subs_avg: number | null; sample_ok: boolean }
interface Report { demo: boolean; records: number; totals: Record<string, number | null>; comparisons: Record<string, Group[]>; recommendations: string[]; limitations: string[] }

const COMP: Record<string, string> = { format: "Shorts × vídeos longos", hook: "Ganchos", theme: "Temas", duration_s: "Durações" };
const TOTALS: [string, string][] = [["views", "Visualizações"], ["impressions", "Impressões"], ["watch_time_h", "Tempo de exibição (h)"], ["subs_gained", "Inscritos"], ["revenue_usd", "Receita (US$)"]];

interface Published { id: string; url: string; title: string; registered_at: string; published_at: string | null; last_error: string | null;
  snapshots: { ts: string; views: number | null; likes: number | null; comments: number | null }[] }

function PublishedVideos() {
  const q = useApi<Published[]>("/analytics/published", 30000);
  const [url, setUrl] = useState("");
  const [msg, setMsg] = useState<{ kind: "success" | "error" | "warn"; text: string } | null>(null);
  const run = async (fn: () => Promise<{ refresh?: { reason: string }; reason?: string }>) => {
    try {
      const r = await fn();
      const reason = r.refresh?.reason ?? r.reason;
      setMsg(reason === "ok" ? { kind: "success", text: "Dados atualizados." } : { kind: "warn", text: `Cadastrado. Coleta automática: ${reason}` });
      q.reload();
    } catch (e) { setMsg({ kind: "error", text: e instanceof Error ? e.message : String(e) }); }
  };
  return (
    <Card title="Vídeos publicados — monitoramento" actions={<Button variant="ghost" onClick={() => run(() => post("/analytics/published/refresh"))}>Atualizar agora</Button>}>
      <form className="mb-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); run(() => post("/analytics/published", { url })); setUrl(""); }}>
        <input className={inputCls} required placeholder="Link do vídeo publicado (ex.: https://www.youtube.com/shorts/...)" value={url} onChange={(e) => setUrl(e.target.value)} />
        <Button type="submit" variant="secondary">Acompanhar</Button>
      </form>
      {msg && <div className="mb-3"><Notice kind={msg.kind}>{msg.text}</Notice></div>}
      <Async q={q}>
        {(vs) => vs.length === 0 ? <Empty>Nenhum vídeo publicado cadastrado.</Empty> : (
          <ul className="space-y-3">
            {vs.map((v) => {
              const last = v.snapshots.at(-1);
              return (
                <li key={v.id} className="rounded-lg border border-line p-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <a className="font-medium text-accent hover:underline" href={v.url} target="_blank" rel="noreferrer">{v.title || v.id}</a>
                    <span className="text-xs text-muted">publicado {fmtDate(v.published_at)} · {v.snapshots.length} coleta(s)</span>
                  </div>
                  {last ? (
                    <div className="mt-2 grid grid-cols-3 gap-2">
                      <Stat label="Visualizações" value={fmtNum(last.views)} /><Stat label="Curtidas" value={fmtNum(last.likes)} /><Stat label="Comentários" value={fmtNum(last.comments)} />
                    </div>
                  ) : null}
                  {v.snapshots.length > 1 && (
                    <table className="mt-2 w-full text-xs"><thead className="text-left text-muted"><tr><th>Coleta</th><th>Visualizações</th><th>Curtidas</th><th>Comentários</th></tr></thead>
                      <tbody>{[...v.snapshots].reverse().slice(0, 12).map((s) => <tr key={s.ts}><td>{fmtDate(s.ts)}</td><td>{fmtNum(s.views)}</td><td>{fmtNum(s.likes)}</td><td>{fmtNum(s.comments)}</td></tr>)}</tbody></table>
                  )}
                  {v.last_error && <p className="mt-2 text-xs text-amber-300">{v.last_error}</p>}
                </li>
              );
            })}
          </ul>
        )}
      </Async>
      <p className="mt-3 text-xs text-muted">Dados públicos (API oficial do YouTube, a cada 6 h). Retenção, CTR e impressões só existem no YouTube Studio: importe o CSV acima.</p>
    </Card>
  );
}

export default function Analytics() {
  const [demo, setDemo] = useState(false);
  const q = useApi<{ report: Report }>(`/analytics?demo=${demo}`);
  const [msg, setMsg] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  async function upload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await post<{ imported: number }>("/analytics/import", fd);
      setMsg({ kind: "success", text: `${r.imported} vídeos importados.` });
      setDemo(false);
      q.reload();
    } catch (err) {
      setMsg({ kind: "error", text: err instanceof Error ? err.message : String(err) });
    }
    e.target.value = "";
  }

  return (
    <>
      <PageHeader title="Analytics" subtitle="Somente métricas reais importadas ou autorizadas. Nada é estimado." actions={
        <>
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium hover:bg-blue-500">
            <Upload className="h-4 w-4" /> Importar CSV do YouTube Studio
            <input type="file" accept=".csv,text/csv" className="sr-only" onChange={upload} />
          </label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={demo} onChange={(e) => setDemo(e.target.checked)} /> Modo demonstração</label>
        </>} />
      {msg && <div className="mb-4"><Notice kind={msg.kind}>{msg.text}</Notice></div>}
      <div className="mb-6"><PublishedVideos /></div>
      {demo &&<div className="mb-4"><Notice kind="warn"><b>MODO DEMONSTRAÇÃO:</b> dados sintéticos gerados localmente. Não representam nenhum canal real.</Notice></div>}
      <Async q={q}>
        {({ report: r }) => r.records === 0 ? (
          <Empty>Nenhuma métrica real importada. Exporte o relatório de conteúdo do YouTube Studio (CSV) e importe aqui, ou ative o modo demonstração para ver a interface.</Empty>
        ) : (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
              {TOTALS.filter(([k]) => r.totals[k] !== null).map(([k, l]) => <Stat key={k} label={l} value={fmtNum(r.totals[k], 1)} />)}
            </div>
            <div className="grid gap-6 lg:grid-cols-2">
              {Object.entries(r.comparisons).map(([key, groups]) => {
                const max = Math.max(1, ...groups.map((g) => g.views_avg ?? 0));
                return (
                  <Card key={key} title={COMP[key] ?? key}>
                    {groups.length === 0 ? <Empty>Sem dados.</Empty> : (
                      <table className="w-full text-sm">
                        <thead className="text-left text-xs uppercase text-muted"><tr><th className="py-1">Grupo</th><th>n</th><th className="w-1/3">Visualizações médias</th><th>CTR</th><th>% assistida</th></tr></thead>
                        <tbody>{groups.map((g) => (
                          <tr key={g.group} className={g.sample_ok ? "" : "text-muted"}>
                            <td className="py-1">{g.group}{!g.sample_ok && " *"}</td><td>{g.n}</td>
                            <td><div className="flex items-center gap-2"><span className="w-16">{fmtNum(g.views_avg)}</span><Bar value={g.views_avg} max={max} /></div></td>
                            <td>{g.ctr_avg ?? "—"}</td><td>{g.avg_view_pct ?? "—"}</td>
                          </tr>
                        ))}</tbody>
                      </table>
                    )}
                    <p className="mt-2 text-xs text-muted">* amostra insuficiente (&lt; 3 vídeos)</p>
                  </Card>
                );
              })}
            </div>
            <Card title="Recomendações e limitações">
              <ul className="list-disc space-y-1 pl-5 text-sm">{r.recommendations.map((x) => <li key={x}>{x}</li>)}</ul>
              <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-muted">{r.limitations.map((x) => <li key={x}>{x}</li>)}</ul>
            </Card>
          </div>
        )}
      </Async>
    </>
  );
}
