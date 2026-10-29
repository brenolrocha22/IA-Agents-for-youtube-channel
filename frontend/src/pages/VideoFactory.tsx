import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Ban, RotateCcw } from "lucide-react";
import { fmtDate, mediaUrl, post, useApi, type Job, type QualityReport, type Task, type Workflow } from "../api";
import Approvals from "../components/Approvals";
import { Async, Badge, Bar, Button, Card, Empty, PageHeader, StatusBadge } from "../components/ui";
import { QualityList } from "../components/Review";
import VisualPlanPanel from "../components/VisualPlan";

const STEP_LABEL: Record<string, string> = {
  research_topic: "Pesquisa", kitchen_story: "Dossiê", visual_hunt: "Visual Hunter", build_brief: "Briefing", write_script: "Roteiro", kitchen_script: "Roteiro",
  retention_review: "Retenção", fact_review: "Revisão factual", editorial_approval: "Aprovação editorial", produce_video: "Produção",
  technical_qa: "Verificação técnica", final_approval: "Aprovação final", publish_prep: "Pacote de publicação",
};

function Pipeline({ wf }: { wf: Workflow }) {
  const q = useApi<{ workflow: Workflow; tasks: Task[] }>(`/workflows/${wf.id}`, 3000);
  const jobs = useApi<Job[]>("/jobs", 3000);
  const qa = useApi<QualityReport[]>("/quality", 6000);
  return (
    <Async q={q}>
      {({ tasks }) => {
        const jobId = tasks.find((t) => t.type === "produce_video")?.result?.output.job_id as string | undefined;
        const job = jobs.data?.find((j) => j.id === jobId) ?? jobs.data?.find((j) => tasks.some((t) => t.type === "produce_video" && t.status === "running") && j.status === "running");
        const report = qa.data?.find((r) => r.target_id === job?.id);
        const failed = tasks.find((t) => t.status === "failed");
        const planId = tasks.find((t) => t.type === "visual_hunt")?.result?.output.visual_plan_id as string | undefined;
        return (
          <div className="space-y-4">
            <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
              {tasks.map((t, i) => (
                <li key={t.id} className="rounded-lg border border-line bg-panel-2/40 p-2 text-xs">
                  <div className="mb-1 font-medium text-zinc-200">{i + 1}. {STEP_LABEL[t.type] ?? t.type}</div>
                  <StatusBadge status={t.status} />
                  {t.result?.summary && <p className="mt-1 text-muted">{t.result.summary}</p>}
                  {t.errors.at(-1) && <p className="mt-1 break-words text-red-300">{t.errors.at(-1)}</p>}
                </li>
              ))}
            </ol>
            <div className="flex flex-wrap gap-2">
              {failed && <Button variant="ghost" onClick={() => post(`/tasks/${failed.id}/retry`).then(q.reload)}><RotateCcw className="h-4 w-4" /> Repetir etapa com falha</Button>}
              {!["completed", "cancelled", "failed"].includes(q.data!.workflow.status) && <Button variant="danger" onClick={() => post(`/workflows/${wf.id}/cancel`).then(q.reload)}><Ban className="h-4 w-4" /> Cancelar</Button>}
            </div>
            {job && (
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm">Etapa: <b>{job.stage}</b> <StatusBadge status={job.status} /></div>
                  <Bar value={job.progress * 100} color="bg-brand" />
                  {job.outputs.video && (
                    <video controls loop className={`mt-2 rounded-lg border border-line bg-black ${job.orientation === "vertical" ? "max-h-[480px]" : "w-full"}`} src={mediaUrl(job.outputs.video)}>
                      <track kind="captions" srcLang="pt" label="Português" src={mediaUrl(job.outputs.captions)} />
                    </video>
                  )}
                  <ul className="text-xs text-muted">{Object.entries(job.outputs).map(([k, v]) => <li key={k}>{k}: <a className="text-accent hover:underline" href={mediaUrl(v)} target="_blank" rel="noreferrer">{v}</a></li>)}</ul>
                </div>
                <div className="space-y-3">
                  <div>
                    <h3 className="mb-1 text-xs font-semibold uppercase text-muted">Log resumido</h3>
                    <ul className="max-h-40 overflow-y-auto rounded-lg bg-black/30 p-2 font-mono text-xs">{job.log.map((l, i) => <li key={i}>{l}</li>)}</ul>
                  </div>
                  <div>
                    <h3 className="mb-1 text-xs font-semibold uppercase text-muted">Manifesto de direitos</h3>
                    <ul className="space-y-1 text-xs">{job.rights_manifest.map((r) => <li key={r.asset}><Badge color={r.status === "ok" ? "green" : "yellow"}>{r.status}</Badge> <b>{r.asset}</b>: {r.license}</li>)}</ul>
                  </div>
                </div>
              </div>
            )}
            {report && <QualityList report={report} />}
            {planId && (
              <details className="rounded-lg border border-line p-3">
                <summary className="cursor-pointer text-sm font-semibold">Narração → vídeo selecionado (plano visual)</summary>
                <div className="mt-3"><VisualPlanPanel planId={planId} /></div>
              </details>
            )}
          </div>
        );
      }}
    </Async>
  );
}

export default function VideoFactory() {
  const q = useApi<Workflow[]>("/workflows", 4000);
  const [params] = useSearchParams();
  const [open, setOpen] = useState<string | null>(null);
  const videos = (q.data ?? []).filter((w) => ["video", "kitchen_short", "script_short"].includes(w.kind));
  return (
    <>
      <PageHeader title="Video Factory" subtitle="Fila de produção, etapas, arquivos renderizados e aprovações. Nada é publicado automaticamente." />
      <div className="space-y-6">
        <Card title="Aprovações pendentes"><Approvals onChange={q.reload} focusTask={params.get("task")} /></Card>
        <Card title="Fila de produção">
          <Async q={q}>
            {() => videos.length === 0 ? <Empty>Nenhum vídeo na fila. Crie um Short no Content Studio.</Empty> : (
              <ul className="divide-y divide-line">
                {videos.map((w) => (
                  <li key={w.id} className="py-3">
                    <button className="flex w-full flex-wrap items-center gap-3 text-left" onClick={() => setOpen(open === w.id ? null : w.id)} aria-expanded={open === w.id}>
                      <span className="min-w-0 flex-1 truncate font-medium">{w.title}</span>
                      <span className="text-xs text-muted">{fmtDate(w.created_at)}</span>
                      <StatusBadge status={w.status} />
                    </button>
                    {open === w.id && <div className="mt-3"><Pipeline wf={w} /></div>}
                  </li>
                ))}
              </ul>
            )}
          </Async>
        </Card>
      </div>
    </>
  );
}
