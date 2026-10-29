import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Check, Eye, MousePointerClick, PencilLine, Repeat, Save, X } from "lucide-react";
import { mediaUrl, post, put, useApi, type Job, type QualityReport, type Script, type Task, type Workflow } from "../api";
import { Async, Badge, Button, Notice, StatusBadge, inputCls } from "./ui";
import SeoPanel from "./SeoPanel";
import VisualPlanPanel from "./VisualPlan";

/** Leva a tela até o campo apontado por uma verificação de qualidade e o destaca. */
export function jumpTo(field: string) {
  const id = `field-${field.replace(":", "-")}`;
  const el = document.getElementById(id);
  if (!el) return false;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.remove("flash");
  void el.offsetWidth; // reinicia a animação
  el.classList.add("flash");
  const input = el.matches("textarea,input") ? el : el.querySelector<HTMLElement>("textarea,input");
  input?.focus({ preventScroll: true });
  return true;
}

const EXTERNAL: Record<string, string> = { story: "/kitchen", scenes: "/kitchen" };

export function QualityList({ report }: { report: QualityReport }) {
  return (
    <div className="rounded-lg border border-line p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-sm font-semibold">
        Quality & Compliance {report.blocking ? <Badge color="red">bloqueia aprovação</Badge> : <Badge color="green">liberado</Badge>}
        <span className="flex items-center gap-1 text-xs font-normal text-muted"><MousePointerClick className="h-3 w-3" /> clique num alerta para ir ao ponto exato</span>
      </div>
      <ul className="space-y-1 text-sm">
        {report.checks.map((c) => {
          const target = c.status !== "pass" ? c.field : null;
          const body = <><StatusBadge status={c.status} /><span><b>{c.label}:</b> {c.detail}</span></>;
          if (target && EXTERNAL[target]) return <li key={c.code}><Link to={EXTERNAL[target]} className="flex gap-2 rounded p-1 hover:bg-panel-2">{body}<span className="text-xs text-accent">abrir dossiê →</span></Link></li>;
          return (
            <li key={c.code}>
              {target ? <button type="button" onClick={() => jumpTo(target)} className="flex w-full gap-2 rounded p-1 text-left hover:bg-panel-2">{body}<span className="ml-auto shrink-0 text-xs text-accent">ir →</span></button>
                : <div className="flex gap-2 p-1">{body}</div>}
            </li>
          );
        })}
      </ul>
      <p className="mt-2 text-xs text-muted">{report.disclaimer}</p>
    </div>
  );
}

/** Editor de título, descrição, data e narração. Salvar dispara nova revisão do Quality & Compliance. */
export function ScriptEditor({ id, onSaved, showQuality = true }: { id: string; onSaved?: () => void; showQuality?: boolean }) {
  const q = useApi<{ script: Script; quality: QualityReport | null }>(`/scripts/${id}`);
  const [draft, setDraft] = useState<Script | null>(null);
  const [quality, setQuality] = useState<QualityReport | null>(null);
  const [msg, setMsg] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  useEffect(() => { if (q.data) { setDraft(q.data.script); setQuality(q.data.quality); } }, [q.data]);
  const locked = draft?.status === "approved";

  async function save() {
    if (!draft) return;
    try {
      const r = await put<{ script: Script; quality: QualityReport }>(`/scripts/${id}`, {
        title: draft.title, description: draft.description, planned_date: draft.planned_date ?? "",
        sections: locked ? undefined : draft.sections.map((s) => ({ narration: s.narration })),
      });
      setDraft(r.script);
      setQuality(r.quality);
      setMsg({ kind: "success", text: "Salvo. O Quality & Compliance revisou novamente o texto." });
      onSaved?.();
    } catch (e) {
      setMsg({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    }
  }

  return (
    <Async q={q}>
      {() => !draft ? null : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={draft.status} />{draft.loop && <Badge color="blue"><Repeat className="mr-1 h-3 w-3" />loop</Badge>}
            <Badge>~{Math.round(draft.est_duration_s)}s</Badge><Badge>provedor: {draft.provider}</Badge>
            {draft.edited_by_human && <Badge color="green">editado por você</Badge>}
            <span className="ml-auto"><Button onClick={save}><Save className="h-4 w-4" /> Salvar e revisar</Button></span>
          </div>
          {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
          {locked && <Notice kind="info">A narração já foi aprovada e está travada. Título e descrição continuam editáveis. Para mudar a narração, use “Editar e refazer”.</Notice>}
          <div className="grid gap-3 md:grid-cols-3">
            <div id="field-title" className="rounded-lg md:col-span-2">
              <label className="mb-1 block text-xs text-muted" htmlFor={`title-${id}`}>Título</label>
              <input id={`title-${id}`} className={inputCls} value={draft.title} maxLength={100} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
              <div className="mt-1 flex flex-wrap gap-2">{draft.title_variants.map((t) => <button key={t} type="button" className="text-xs text-accent hover:underline" onClick={() => setDraft({ ...draft, title: t })}>{t}</button>)}</div>
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted" htmlFor={`date-${id}`}>Data planejada</label>
              <input id={`date-${id}`} type="date" className={inputCls} value={draft.planned_date ?? ""} onChange={(e) => setDraft({ ...draft, planned_date: e.target.value })} />
            </div>
          </div>
          <div className="space-y-3">
            {draft.sections.map((s, i) => (
              <div key={i} id={`field-section-${i}`} className="rounded-lg border border-line bg-panel-2/40 p-3">
                <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-muted"><Badge color={s.kind === "hook" || s.kind === "loop" ? "red" : "gray"}>{i + 1}. {s.heading}</Badge> ~{s.est_seconds}s · texto na tela: “{s.on_screen_text}”</div>
                <textarea aria-label={`Narração: ${s.heading}`} className={`${inputCls} min-h-16`} value={s.narration} disabled={locked}
                  onChange={(e) => setDraft({ ...draft, sections: draft.sections.map((x, j) => j === i ? { ...x, narration: e.target.value } : x) })} />
                <p className="mt-1 text-xs text-muted">Visual: {s.visual_note}</p>
              </div>
            ))}
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div id="field-description" className="rounded-lg">
              <label className="mb-1 block text-xs text-muted" htmlFor={`desc-${id}`}>Descrição do YouTube</label>
              <textarea id={`desc-${id}`} className={`${inputCls} min-h-48`} value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
              <p className="mt-1 text-xs text-muted">{draft.hashtags.join(" ")}</p>
            </div>
            <div className="space-y-3 text-sm">
              <div><h3 className="mb-1 text-xs font-semibold uppercase text-muted">Ideias de capa</h3><ul className="list-disc pl-5">{draft.thumbnail_ideas.map((t) => <li key={t}>{t}</li>)}</ul></div>
              <div><h3 className="mb-1 text-xs font-semibold uppercase text-muted">Retenção</h3><ul className="list-disc pl-5">{draft.retention_notes.map((t) => <li key={t}>{t}</li>)}</ul></div>
              <div id="field-sources" className="rounded-lg"><h3 className="mb-1 text-xs font-semibold uppercase text-muted">Fontes</h3><ul>{draft.sources.map((s) => <li key={s.id}><a className="text-accent hover:underline" href={s.url} target="_blank" rel="noreferrer">{s.title}</a> <span className="text-xs text-muted">{s.license}</span></li>)}</ul></div>
              {draft.rights_notes.length > 0 && <div><h3 className="mb-1 text-xs font-semibold uppercase text-muted">Direitos</h3><ul className="list-disc pl-5 text-xs">{draft.rights_notes.map((t) => <li key={t}>{t}</li>)}</ul></div>}
            </div>
          </div>
          {showQuality && quality && <QualityList report={quality} />}
        </div>
      )}
    </Async>
  );
}

/** Player com legendas. Avisa quando o vídeo foi assistido até o fim (≥ 90%). */
export function VideoPreview({ job, onWatched }: { job: Job; onWatched?: () => void }) {
  const ref = useRef<HTMLVideoElement>(null);
  const [srt, setSrt] = useState<string>("");
  const done = useRef(false);
  useEffect(() => {
    if (job.outputs.captions) fetch(mediaUrl(job.outputs.captions)).then((r) => r.text()).then(setSrt).catch(() => setSrt(""));
  }, [job.outputs.captions]);
  const vertical = job.orientation === "vertical";
  return (
    <div className="grid gap-4 lg:grid-cols-[auto_1fr]">
      <div id="field-video" className="rounded-lg">
        <video ref={ref} controls playsInline className={`rounded-lg border border-line bg-black ${vertical ? "h-[560px] max-h-[70vh] w-auto" : "w-full"}`}
          src={mediaUrl(job.outputs.video)} poster={job.outputs.cover ? mediaUrl(job.outputs.cover) : undefined}
          onTimeUpdate={(e) => { const v = e.currentTarget; if (!done.current && v.duration && v.currentTime / v.duration >= 0.9) { done.current = true; onWatched?.(); } }} />
      </div>
      <div className="min-w-0 space-y-3">
        {job.outputs.cover && <div><h3 className="mb-1 text-xs font-semibold uppercase text-muted">Capa gerada</h3><img src={mediaUrl(job.outputs.cover)} alt="Capa do vídeo" className="h-48 rounded-lg border border-line" /></div>}
        <div id="field-captions" className="rounded-lg">
          <h3 className="mb-1 text-xs font-semibold uppercase text-muted">Legendas (embutidas no vídeo)</h3>
          <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded-lg bg-black/30 p-2 text-xs">{srt || "—"}</pre>
        </div>
        <div id="field-rights" className="rounded-lg">
          <h3 className="mb-1 text-xs font-semibold uppercase text-muted">Manifesto de direitos</h3>
          <ul className="space-y-1 text-xs">{job.rights_manifest.map((r) => <li key={r.asset}><Badge color={r.status === "ok" ? "green" : "yellow"}>{r.status === "ok" ? "ok" : "verificar"}</Badge> <b>{r.asset}</b>: {r.license}</li>)}</ul>
        </div>
      </div>
    </div>
  );
}

interface Context { task: Task; workflow: Workflow | null; script: Script | null; script_quality: QualityReport | null; job: Job | null; job_quality: QualityReport | null }

/** Revisão completa antes de decidir: ver/ouvir, editar e só então aprovar. */
export function ApprovalReview({ taskId, onDone }: { taskId: string; onDone: () => void }) {
  const q = useApi<Context>(`/tasks/${taskId}/context`);
  const [watched, setWatched] = useState(false);
  const [msg, setMsg] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try { await fn(); setMsg({ kind: "success", text: ok }); onDone(); }
    catch (e) { setMsg({ kind: "error", text: e instanceof Error ? e.message : String(e) }); q.reload(); }
  };

  return (
    <Async q={q}>
      {(c) => {
        const final = c.task.type === "final_approval";
        const canApprove = !final || watched;
        return (
          <div className="space-y-4">
            {msg && <Notice kind={msg.kind}>{msg.text}</Notice>}
            {final && c.job && (
              <>
                <VideoPreview job={c.job} onWatched={() => setWatched(true)} />
                {c.job_quality && <QualityList report={c.job_quality} />}
              </>
            )}
            {final && c.script && (
              <details open className="rounded-lg border border-line p-3">
                <summary className="cursor-pointer text-sm font-semibold">Publicação no YouTube (YouTube SEO Agent)</summary>
                <div className="mt-3"><SeoPanel scriptId={c.script.id} /></div>
              </details>
            )}
            {c.script?.visual_plan_id && (
              <details open className="rounded-lg border border-line p-3">
                <summary className="cursor-pointer text-sm font-semibold">Narração → vídeo selecionado (filmagens reais)</summary>
                <div className="mt-3"><VisualPlanPanel planId={c.script.visual_plan_id} /></div>
              </details>
            )}
            {c.script && (
              <details open={!final} className="rounded-lg border border-line p-3">
                <summary className="cursor-pointer text-sm font-semibold"><PencilLine className="mr-1 inline h-4 w-4" />{final ? "Título, descrição e roteiro" : "Roteiro para revisar e editar"}</summary>
                <div className="mt-3"><ScriptEditor id={c.script.id} onSaved={q.reload} /></div>
              </details>
            )}
            <div className="sticky bottom-0 flex flex-wrap items-center gap-2 border-t border-line bg-panel py-3">
              <Button variant="secondary" disabled={!canApprove} title={canApprove ? "" : "Assista ao vídeo até o fim para liberar"}
                onClick={() => act(() => post(`/tasks/${taskId}/approve`, { note: "" }), final ? "Vídeo aprovado. O pacote para publicação manual será preparado." : "Roteiro aprovado. A produção do vídeo vai começar.")}>
                <Check className="h-4 w-4" /> {final ? "Aprovar vídeo" : "Aprovar roteiro"}
              </Button>
              {!canApprove && <span className="flex items-center gap-1 text-xs text-amber-300"><Eye className="h-3 w-3" /> Assista ao vídeo até o fim para liberar a aprovação.</span>}
              {final && c.workflow && (
                <Button variant="ghost" onClick={() => act(() => post(`/workflows/${c.workflow!.id}/rework`), "Roteiro destravado. Edite em Content Studio ou aqui; ele passará por revisão e aprovação de novo antes de renderizar.")}>
                  <PencilLine className="h-4 w-4" /> Editar narração e refazer vídeo
                </Button>
              )}
              <Button variant="danger" onClick={() => { const note = window.prompt("Motivo da rejeição:") ?? ""; act(() => post(`/tasks/${taskId}/reject`, { note }), "Rejeitado."); }}>
                <X className="h-4 w-4" /> Rejeitar
              </Button>
            </div>
          </div>
        );
      }}
    </Async>
  );
}
