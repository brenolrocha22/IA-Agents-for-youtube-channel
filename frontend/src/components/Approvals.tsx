import { useEffect, useState } from "react";
import { ChevronDown, Eye } from "lucide-react";
import { fmtDate, useApi, type Task, type Workflow } from "../api";
import { ApprovalReview } from "./Review";
import { Async, Badge, Button, Empty } from "./ui";

const LABEL: Record<string, string> = {
  editorial_approval: "Revisar roteiro",
  final_approval: "Assistir e aprovar vídeo",
};

/** Aprovações pendentes. Cada item abre a revisão completa (vídeo, roteiro, relatórios) antes da decisão. */
export default function Approvals({ onChange, focusTask }: { onChange?: () => void; focusTask?: string | null }) {
  const q = useApi<Task[]>("/tasks?status=awaiting_approval", 5000);
  const wfs = useApi<Workflow[]>("/workflows", 10000);
  const [open, setOpen] = useState<string | null>(focusTask ?? null);
  // Vindo do Dashboard: rola até a tarefa pendente assim que a lista carregar.
  useEffect(() => {
    if (focusTask && q.data?.some((t) => t.id === focusTask)) {
      document.getElementById(`approval-${focusTask}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [focusTask, q.data]);
  const title = (t: Task) => wfs.data?.find((w) => w.id === t.workflow_id)?.title ?? t.workflow_id;

  return (
    <Async q={q}>
      {(tasks) => tasks.length === 0 ? <Empty>Nenhuma aprovação pendente.</Empty> : (
        <ul className="divide-y divide-line">
          {tasks.map((t) => (
            <li key={t.id} id={`approval-${t.id}`} className={`py-3 ${t.id === focusTask ? "rounded-lg ring-1 ring-accent/60" : ""}`}>
              <div className="flex flex-wrap items-center gap-3">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{title(t)}</div>
                  <div className="flex items-center gap-2 text-xs text-muted">
                    <Badge color={t.type === "final_approval" ? "blue" : "yellow"}>{LABEL[t.type] ?? t.type}</Badge> desde {fmtDate(t.started_at ?? t.created_at)}
                  </div>
                </div>
                <Button variant={open === t.id ? "ghost" : "secondary"} onClick={() => setOpen(open === t.id ? null : t.id)}>
                  {open === t.id ? <><ChevronDown className="h-4 w-4" /> Fechar</> : <><Eye className="h-4 w-4" /> {t.type === "final_approval" ? "Assistir e revisar" : "Revisar"}</>}
                </Button>
              </div>
              {open === t.id && (
                <div className="mt-3 rounded-xl border border-line bg-base/60 p-3">
                  <ApprovalReview taskId={t.id} onDone={() => { q.reload(); onChange?.(); }} />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Async>
  );
}
