import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Clapperboard, Download, Search, ShieldCheck } from "lucide-react";
import { fmtDate, mediaUrl, post, useApi, type Source } from "../api";
import { Async, Badge, Button, Card, Empty, Notice, PageHeader, Stat, StatusBadge, inputCls } from "../components/ui";

interface Fact { id: string; text: string; category: string; stage: string; source_id: string; verified: boolean; verified_by: string | null; added_by: string; language?: string }
interface Story {
  id: string; show: string; restaurant: string; location: string | null; air_date: string | null; air_year: number | null;
  facts: Fact[]; sources: Source[]; scenes: { stage: string; description: string; visual_type: string }[];
  missing_stages: string[]; editorial_summary: string; rights_notes: string[];
}
interface Episode { id: string; restaurant: string; location: string | null; air_date: string | null; season: number | null; summary: string }
interface Overview {
  shows: { id: string; name: string }[];
  counts: Record<string, number>;
  catalogs: { id: string; show: string; episodes: number; collected_at: string; source: Source }[];
  stories: { id: string; restaurant: string; show: string; air_year: number | null; facts: number; verified: number; missing_stages: string[] }[];
  scripts: { id: string; title: string; status: string; est_duration_s: number }[];
  jobs: { id: string; status: string; stage: string; progress: number; video: string | null }[];
  approvals: { id: string; type: string; workflow_id: string }[];
  pending: { story_id: string; restaurant: string; fact: Fact }[];
  assets: { id: string; name: string; origin: string; license: string; scope: string; restrictions: string }[];
}

const CATEGORY: Record<string, string> = {
  exibido_no_programa: "exibido no programa", declaracao: "declaração", posterior_verificado: "informação posterior", interpretacao_editorial: "interpretação editorial",
};
const STAGE: Record<string, string> = { contexto: "contexto", conflito: "conflito", intervencao: "intervenção", transformacao: "transformação", resultado: "resultado" };

function StoryPanel({ id, onChange }: { id: string; onChange: () => void }) {
  const q = useApi<Story>(`/kitchen/stories/${id}`);
  const [msg, setMsg] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [form, setForm] = useState({ text: "", category: "posterior_verificado", stage: "resultado", source_title: "", source_url: "" });

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try { await fn(); setMsg({ kind: "success", text: ok }); q.reload(); onChange(); }
    catch (e) { setMsg({ kind: "error", text: e instanceof Error ? e.message : String(e) }); }
  };
  const addFact = (e: FormEvent) => { e.preventDefault(); act(() => post(`/kitchen/stories/${id}/facts`, form), "Fato adicionado com fonte."); };

  return (
    <Async q={q}>
      {(s) => (
        <div className="space-y-4">
          <p className="text-sm text-zinc-300">{s.editorial_summary}</p>
          {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => act(() => post(`/kitchen/stories/${id}/short`), "Workflow criado. Acompanhe em Video Factory; a aprovação editorial é sua.")}>
              <Clapperboard className="h-4 w-4" /> Gerar roteiro e Short
            </Button>
            {s.missing_stages.length > 0 && <Badge color="yellow">etapas sem fonte: {s.missing_stages.map((x) => STAGE[x] ?? x).join(", ")}</Badge>}
          </div>
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase text-muted">Fatos ({s.facts.filter((f) => f.verified).length}/{s.facts.length} verificados)</h3>
            <ul className="space-y-2">
              {s.facts.map((f) => (
                <li key={f.id} className="rounded-lg border border-line bg-panel-2/40 p-3 text-sm">
                  <div className="mb-1 flex flex-wrap gap-1"><Badge color="blue">{STAGE[f.stage] ?? f.stage}</Badge><Badge>{CATEGORY[f.category]}</Badge>
                    {f.verified ? <Badge color="green">verificado por {f.verified_by}</Badge> : <Badge color="yellow">pendente</Badge>}
                    {f.language && f.language !== "pt" && <Badge color="blue">em inglês: só referência — adicione o fato em português abaixo</Badge>}</div>
                  <p>{f.text}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
                    <a className="text-accent hover:underline" href={s.sources.find((x) => x.id === f.source_id)?.url} target="_blank" rel="noreferrer">ver fonte</a>
                    <button className="text-zinc-300 hover:underline" onClick={() => act(() => post(`/kitchen/stories/${id}/facts/${f.id}/verify`, { verified: !f.verified }), f.verified ? "Verificação removida." : "Fato marcado como verificado.")}>
                      {f.verified ? "desfazer verificação" : "marcar como verificado (conferi na fonte)"}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
          <form onSubmit={addFact} className="grid gap-2 rounded-lg border border-line p-3 md:grid-cols-2">
            <h3 className="text-xs font-semibold uppercase text-muted md:col-span-2">Adicionar fato verificado (com fonte)</h3>
            <textarea required minLength={10} className={`${inputCls} md:col-span-2`} placeholder="Fato em português, com suas palavras" value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} />
            <select className={inputCls} value={form.stage} onChange={(e) => setForm({ ...form, stage: e.target.value })}>{Object.entries(STAGE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
            <select className={inputCls} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{Object.entries(CATEGORY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
            <input required className={inputCls} placeholder="Título da fonte" value={form.source_title} onChange={(e) => setForm({ ...form, source_title: e.target.value })} />
            <input required type="url" className={inputCls} placeholder="https://…" value={form.source_url} onChange={(e) => setForm({ ...form, source_url: e.target.value })} />
            <div className="md:col-span-2"><Button type="submit" variant="secondary">Adicionar</Button></div>
          </form>
          <div className="grid gap-4 md:grid-cols-2">
            <div><h3 className="mb-1 text-xs font-semibold uppercase text-muted">Cenas e recursos visuais</h3>
              <ul className="space-y-1 text-sm">{s.scenes.map((c, i) => <li key={i}><Badge color={c.visual_type === "material_terceiros" ? "red" : "green"}>{c.visual_type}</Badge> {c.description}</li>)}</ul></div>
            <div><h3 className="mb-1 text-xs font-semibold uppercase text-muted">Observações de direitos</h3>
              <ul className="list-disc space-y-1 pl-5 text-sm text-zinc-300">{s.rights_notes.map((r) => <li key={r}>{r}</li>)}</ul></div>
          </div>
        </div>
      )}
    </Async>
  );
}

export default function Kitchen() {
  const q = useApi<Overview>("/kitchen/overview", 6000);
  const [show, setShow] = useState("pesadelo_br");
  const [search, setSearch] = useState("");
  const eps = useApi<Episode[]>(`/kitchen/episodes?show_id=${show}&q=${encodeURIComponent(search)}`);
  const [story, setStory] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [asset, setAsset] = useState({ name: "", origin: "", license: "", scope: "", restrictions: "" });

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    try { await fn(); setMsg({ kind: "success", text: ok }); q.reload(); eps.reload(); }
    catch (e) { setMsg({ kind: "error", text: e instanceof Error ? e.message : String(e) }); }
  };

  return (
    <>
      <PageHeader title="Reality Kitchen Stories" subtitle="Crises e transformações de restaurantes em reality shows, contadas com narração e visuais originais. Nenhuma cena dos programas é usada."
        actions={<Button onClick={() => run(() => post("/kitchen/catalog", { show_id: show }), "Coleta do catálogo iniciada.")}><Download className="h-4 w-4" /> Atualizar catálogo</Button>} />
      {msg && <div className="mb-4"><Notice kind={msg.kind}>{msg.text}</Notice></div>}
      <Async q={q}>
        {(o) => (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4 xl:grid-cols-8">
              <Stat label="Episódios" value={o.counts.episodes} /><Stat label="Restaurantes" value={o.counts.restaurants} />
              <Stat label="Dossiês" value={o.counts.stories} /><Stat label="A verificar" value={o.counts.pending_verification} tone={o.counts.pending_verification ? "red" : "default"} />
              <Stat label="Roteiros" value={o.counts.scripts} /><Stat label="Em produção" value={o.counts.in_production} tone="blue" />
              <Stat label="Aprovações" value={o.counts.approvals} tone={o.counts.approvals ? "red" : "default"} /><Stat label="Concluídos" value={o.counts.videos_done} />
            </div>

            <div className="grid gap-6 lg:grid-cols-3">
              <Card title="Episódios pesquisados" className="lg:col-span-1">
                <div className="mb-3 flex gap-2">
                  <select aria-label="Programa" className={`${inputCls} w-auto`} value={show} onChange={(e) => setShow(e.target.value)}>{o.shows.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
                </div>
                <div className="relative mb-2"><Search className="absolute left-2 top-2.5 h-4 w-4 text-muted" /><input className={`${inputCls} pl-8`} placeholder="Restaurante ou cidade" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
                <Async q={eps}>
                  {(list) => list.length === 0 ? <Empty>Catálogo vazio. Clique em “Atualizar catálogo”.</Empty> : (
                    <ul className="max-h-[520px] divide-y divide-line overflow-y-auto">
                      {list.map((e) => (
                        <li key={e.id} className="py-2 text-sm">
                          <div className="font-medium">{e.restaurant}</div>
                          <div className="text-xs text-muted">{e.location} · {e.air_date} · T{e.season}</div>
                          <button disabled={!e.summary} className="mt-1 text-xs text-accent hover:underline disabled:text-muted disabled:no-underline"
                            onClick={() => run(async () => { const s = await post<Story>("/kitchen/stories", { episode_id: e.id }); setStory(s.id); }, "Dossiê criado. Verifique os fatos na fonte antes de gerar o roteiro.")}>
                            {e.summary ? "Criar dossiê" : "sem resumo na fonte"}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </Async>
                {o.catalogs.map((c) => <p key={c.id} className="mt-2 text-xs text-muted">Fonte: <a className="text-accent" href={c.source.url} target="_blank" rel="noreferrer">{c.source.title}</a> · {fmtDate(c.collected_at)}</p>)}
              </Card>

              <Card title="Dossiê" className="lg:col-span-2" actions={
                <select aria-label="Dossiê" className={`${inputCls} w-auto py-1`} value={story ?? ""} onChange={(e) => setStory(e.target.value || null)}>
                  <option value="">Selecione…</option>{o.stories.map((s) => <option key={s.id} value={s.id}>{s.restaurant} ({s.verified}/{s.facts})</option>)}
                </select>}>
                {story ? <StoryPanel key={story} id={story} onChange={q.reload} /> : <Empty>Crie ou selecione um dossiê.</Empty>}
              </Card>
            </div>

            <div className="grid gap-6 lg:grid-cols-3">
              <Card title="Roteiros e vídeos">
                {o.scripts.length === 0 ? <Empty>Nenhum roteiro.</Empty> : (
                  <ul className="space-y-2 text-sm">{o.scripts.map((s) => <li key={s.id} className="flex items-center gap-2"><StatusBadge status={s.status} /><span className="flex-1 truncate">{s.title}</span><span className="text-xs text-muted">~{Math.round(s.est_duration_s)}s</span></li>)}</ul>
                )}
                <ul className="mt-3 space-y-1 text-sm">{o.jobs.map((j) => <li key={j.id} className="flex items-center gap-2"><StatusBadge status={j.status} /> {j.stage}
                  {j.video && <a className="text-accent hover:underline" href={mediaUrl(j.video)} target="_blank" rel="noreferrer">abrir vídeo</a>}</li>)}</ul>
                {o.approvals.length > 0 && <p className="mt-3 text-sm"><Link to="/factory" className="text-accent hover:underline">{o.approvals.length} aprovação(ões) aguardando você →</Link></p>}
              </Card>
              <Card title="Pendências de verificação">
                {o.pending.length === 0 ? <Empty><CheckCircle2 className="h-4 w-4" /> Nada pendente.</Empty> : (
                  <ul className="max-h-72 space-y-2 overflow-y-auto text-sm">{o.pending.map((p) => <li key={p.fact.id}><button className="text-left hover:underline" onClick={() => setStory(p.story_id)}><b>{p.restaurant}:</b> {p.fact.text}</button></li>)}</ul>
                )}
              </Card>
              <Card title="Materiais autorizados">
                {o.assets.length === 0 ? <p className="mb-3 text-sm text-muted">Nenhum material de terceiros registrado. Os vídeos usam apenas visuais originais.</p> : (
                  <ul className="mb-3 space-y-2 text-sm">{o.assets.map((a) => <li key={a.id}><ShieldCheck className="mr-1 inline h-4 w-4 text-emerald-400" /><b>{a.name}</b> — {a.license}; escopo: {a.scope}{a.restrictions && `; restrições: ${a.restrictions}`}<div className="text-xs text-muted">{a.origin}</div></li>)}</ul>
                )}
                <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); run(() => post("/kitchen/assets", asset), "Material registrado."); }}>
                  {(["name", "origin", "license", "scope", "restrictions"] as const).map((k) => (
                    <input key={k} required={k !== "restrictions"} className={inputCls} value={asset[k]} onChange={(e) => setAsset({ ...asset, [k]: e.target.value })}
                      placeholder={{ name: "Nome do material", origin: "Origem (quem autorizou / onde)", license: "Licença ou contrato", scope: "Escopo permitido", restrictions: "Restrições (opcional)" }[k]} />
                  ))}
                  <Button type="submit" variant="ghost">Registrar autorização</Button>
                </form>
              </Card>
            </div>
          </div>
        )}
      </Async>
    </>
  );
}
