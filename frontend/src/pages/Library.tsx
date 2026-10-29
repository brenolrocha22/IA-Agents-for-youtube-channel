import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ExternalLink, Play, X } from "lucide-react";
import { fmtDate, fmtNum, mediaUrl, post, useApi } from "../api";
import { Async, Badge, Button, Empty, Notice, PageHeader, inputCls } from "../components/ui";

interface Item {
  script_id: string; job_id: string; title: string; channel_id: string | null; created_at: string; duration_s: number | null;
  status: "publicado" | "pronto para postar" | "aguardando aprovação" | "renderizado"; video: string; cover: string | null; captions: string | null;
  qa_blocking: boolean | null; workflow_id: string | null; final_task_id: string | null; package: string | null;
  published: { url: string; views: number | null; likes: number | null; comments: number | null; checked_at: string | null; note: string | null } | null;
}

const STATUS_COLOR = { publicado: "green", "pronto para postar": "blue", "aguardando aprovação": "yellow", renderizado: "gray" } as const;
const TABS = [["todos", "Todos"], ["concluidos", "Concluídos"], ["publicados", "Publicados"]] as const;
const channelName = (id: string | null) => (id === "clips_plus" ? "Clip+" : id === "natureza" ? "Clip+ Nat" : "—");

/** Prévia do vídeo + detalhes; permite marcar como publicado com o link do YouTube. */
function Preview({ item, onClose, onChange }: { item: Item; onClose: () => void; onChange: () => void }) {
  const [url, setUrl] = useState("");
  const [msg, setMsg] = useState<{ kind: "success" | "error" | "warn"; text: string } | null>(null);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);
  async function markPublished() {
    try {
      const r = await post<{ refresh: { reason: string } }>("/analytics/published", { url, script_id: item.script_id });
      setMsg(r.refresh.reason === "ok" ? { kind: "success", text: "Marcado como publicado e números coletados." }
        : { kind: "warn", text: `Marcado como publicado. Coleta automática: ${r.refresh.reason}` });
      onChange();
    } catch (e) { setMsg({ kind: "error", text: e instanceof Error ? e.message : String(e) }); }
  }
  const p = item.published;
  return (
    <div role="dialog" aria-modal="true" aria-label={`Prévia: ${item.title}`} className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4" onClick={onClose}>
      <div className="flex max-h-full w-full max-w-4xl flex-col gap-4 overflow-y-auto rounded-xl border border-line bg-panel p-4 md:flex-row" onClick={(e) => e.stopPropagation()}>
        <video controls autoPlay playsInline className="mx-auto max-h-[80vh] rounded-lg bg-black md:w-[340px]" src={mediaUrl(item.video)} poster={item.cover ? mediaUrl(item.cover) : undefined}>
          {item.captions && <track kind="captions" srcLang="pt" label="Português" src={mediaUrl(item.captions)} />}
        </video>
        <div className="min-w-0 flex-1 space-y-3 text-sm">
          <div className="flex items-start gap-2">
            <h2 className="flex-1 text-lg font-semibold">{item.title}</h2>
            <button aria-label="Fechar" onClick={onClose} className="rounded p-1 hover:bg-panel-2"><X className="h-5 w-5" /></button>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge color={STATUS_COLOR[item.status]}>{item.status}</Badge><Badge>{channelName(item.channel_id)}</Badge>
            {item.duration_s && <Badge>{item.duration_s.toFixed(0)}s</Badge>}
            {item.qa_blocking !== null && <Badge color={item.qa_blocking ? "red" : "green"}>{item.qa_blocking ? "QA bloqueado" : "QA liberado"}</Badge>}
          </div>
          <p className="text-xs text-muted">Renderizado em {fmtDate(item.created_at)} · arquivo: <code>{item.video}</code></p>
          {item.package && <p className="text-xs">Pacote para postar: <code>{item.package}</code> (inclui <b>youtube.txt</b> com título, descrição, tags e comentário fixado)</p>}
          {item.final_task_id && <Link className="text-accent hover:underline" to={`/factory?task=${item.final_task_id}`}>Aprovar este vídeo na Video Factory →</Link>}
          {p ? (
            <div className="space-y-2 rounded-lg border border-line p-3">
              <a href={p.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent hover:underline"><ExternalLink className="h-4 w-4" /> Ver no YouTube</a>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div><div className="text-xs text-muted">Visualizações</div><div className="text-lg font-semibold">{fmtNum(p.views)}</div></div>
                <div><div className="text-xs text-muted">Curtidas</div><div className="text-lg font-semibold">{fmtNum(p.likes)}</div></div>
                <div><div className="text-xs text-muted">Comentários</div><div className="text-lg font-semibold">{fmtNum(p.comments)}</div></div>
              </div>
              <p className="text-xs text-muted">{p.checked_at ? `Atualizado em ${fmtDate(p.checked_at)}` : p.note ?? "Aguardando primeira coleta."}</p>
            </div>
          ) : (
            <form className="space-y-2 rounded-lg border border-line p-3" onSubmit={(e) => { e.preventDefault(); markPublished(); }}>
              <label className="block text-xs text-muted" htmlFor="pub-url">Já postou? Cole o link do YouTube para acompanhar os resultados</label>
              <input id="pub-url" className={inputCls} required placeholder="https://www.youtube.com/shorts/..." value={url} onChange={(e) => setUrl(e.target.value)} />
              <Button type="submit" variant="secondary">Marcar como publicado</Button>
            </form>
          )}
          {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
        </div>
      </div>
    </div>
  );
}

export default function Library() {
  const q = useApi<Item[]>("/library", 30000);
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("todos");
  const [open, setOpen] = useState<Item | null>(null);
  return (
    <>
      <PageHeader title="Vídeos" subtitle="Tudo o que já foi produzido: assista à prévia, veja o que está pronto para postar e os resultados dos publicados." />
      <div className="mb-4 flex gap-1" role="tablist">
        {TABS.map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={`rounded-lg px-3 py-1.5 text-sm ${tab === k ? "bg-accent text-white" : "border border-line hover:bg-panel-2"}`}>{l}</button>
        ))}
      </div>
      <Async q={q}>
        {(items) => {
          const list = items.filter((i) => tab === "todos" || (tab === "publicados" ? i.status === "publicado" : i.status !== "publicado"));
          if (list.length === 0) return <Empty>{tab === "publicados" ? "Nenhum vídeo marcado como publicado ainda." : "Nenhum vídeo renderizado."}</Empty>;
          return (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
              {list.map((i) => (
                <button key={i.job_id} onClick={() => setOpen(i)} className="group overflow-hidden rounded-xl border border-line bg-panel text-left transition hover:-translate-y-0.5 hover:border-accent">
                  <div className="relative aspect-[9/16] bg-black">
                    {i.cover ? <img src={mediaUrl(i.cover)} alt="" className="h-full w-full object-cover" loading="lazy" />
                      : <video src={`${mediaUrl(i.video)}#t=2`} muted preload="metadata" className="h-full w-full object-cover" />}
                    <span className="absolute inset-0 flex items-center justify-center bg-black/0 transition group-hover:bg-black/40">
                      <Play className="h-12 w-12 text-white opacity-0 transition group-hover:opacity-100" />
                    </span>
                    {i.duration_s && <span className="absolute bottom-2 right-2 rounded bg-black/70 px-1.5 text-xs">{i.duration_s.toFixed(0)}s</span>}
                  </div>
                  <div className="space-y-1 p-2">
                    <div className="line-clamp-2 text-sm font-medium">{i.title}</div>
                    <div className="flex flex-wrap items-center gap-1 text-xs"><Badge color={STATUS_COLOR[i.status]}>{i.status}</Badge><span className="text-muted">{channelName(i.channel_id)}</span></div>
                    {i.published && <div className="text-xs text-muted">{fmtNum(i.published.views)} visualizações</div>}
                  </div>
                </button>
              ))}
            </div>
          );
        }}
      </Async>
      {open && <Preview item={open} onClose={() => setOpen(null)} onChange={() => { q.reload(); }} />}
    </>
  );
}
