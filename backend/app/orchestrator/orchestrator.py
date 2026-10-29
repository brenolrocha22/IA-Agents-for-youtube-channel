"""Agente 1 — Orchestrator: único componente que altera o estado de tarefas e workflows.

Não pode alterar a política (instância imutável) nem conceder permissões: aprovações vêm apenas de
chamadas humanas à API (`approve` / `reject`).
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..agents import AGENTS, TASK_ROUTES
from ..agents.base import AgentContext
from ..config import Policy, get_policy
from ..models import (TERMINAL, ExecutionLimits, QualityReport, Script, Task, TaskResult, TaskStatus, Workflow, now)
from ..research.http import ApiBudget
from ..store import Store, get_store

APPROVAL_GATES = {"editorial_approval": "script_id", "final_approval": "job_id"}


class ApprovalBlocked(RuntimeError):
    pass


def _video_plan(p: dict[str, Any]) -> list[tuple[str, str, list[str], dict]]:
    """(chave, tipo, dependências, entrada)."""
    base = {k: p[k] for k in ("topic", "niche_id", "format", "tone", "language", "channel_id", "items") if k in p}
    return [
        ("research", "research_topic", [], base),
        ("brief", "build_brief", ["research"], {}),
        ("script", "write_script", ["brief"], {}),
        *_production_tail(p),
    ]


def _production_tail(p: dict[str, Any], visual_done: bool = False) -> list[tuple[str, str, list[str], dict]]:
    """Etapas comuns a partir de um roteiro: [busca visual] → revisão → aprovação → produção → QA → aprovação → pacote.

    Visual First: em canais que exigem filmagem real, o Visual Hunter roda antes da aprovação editorial,
    para que a cobertura visual seja revisada junto com o texto.
    """
    visual = p.get("require_footage") and not visual_done
    editorial_deps = ["retention", "facts"] + (["visual"] if visual else [])
    return [
        *([("visual", "visual_hunt", ["script"], {})] if visual else []),
        ("retention", "retention_review", ["script"], {}),
        ("facts", "fact_review", ["script"], {}),
        ("editorial", "editorial_approval", editorial_deps, {}),
        ("produce", "produce_video", ["editorial"], {"orientation": p.get("orientation")} if p.get("orientation") else {}),
        ("qa", "technical_qa", ["produce"], {}),
        ("final", "final_approval", ["qa"], {}),
        ("package", "publish_prep", ["final"], {}),
    ]


def _plan(kind: str, p: dict[str, Any]) -> list[tuple[str, str, list[str], dict]]:
    if kind == "video":
        return _video_plan(p)
    if kind == "niche_research":
        return [("rank", "rank_niches", [], {"markets": p.get("markets", ["pt", "en"])}),
                ("trends_pt", "collect_trends", [], {"lang": "pt", "days": p.get("days", 7)}),
                ("trends_en", "collect_trends", [], {"lang": "en", "days": p.get("days", 7)})]
    if kind == "kitchen_catalog":
        return [("catalog", "kitchen_catalog", [], {"show_id": p.get("show_id", "pesadelo_br")})]
    if kind == "kitchen_short":
        return [("script", "kitchen_script", [], {"story_id": p["story_id"]}), *_production_tail(p)]
    if kind == "script_short":  # roteiro escrito pelo proprietário: busca visual primeiro
        return [("script", "visual_hunt", [], {"script_id": p["script_id"]}), *_production_tail(p, visual_done=True)]
    if kind == "analytics":
        return [("report", "analytics_report", [], {"demo": bool(p.get("demo"))})]
    raise ValueError(f"Tipo de workflow desconhecido: {kind}")


class Orchestrator:
    name = "orchestrator"

    def __init__(self, store: Store | None = None, policy: Policy | None = None):
        self.store = store or get_store()
        self.policy = policy or get_policy()
        self._lock = threading.RLock()
        self._budgets: dict[str, ApiBudget] = {}
        self._inflight: set[str] = set()
        self._cancel: dict[str, threading.Event] = {}
        self._pool: ThreadPoolExecutor | None = None
        self._runner: threading.Thread | None = None
        self._stop = threading.Event()

    # ---------- criação ----------
    def create_workflow(self, kind: str, params: dict[str, Any], title: str | None = None) -> Workflow:
        plan = _plan(kind, params)
        if len(plan) > self.policy.limits.max_tasks_per_run:
            raise ValueError("Workflow excede o limite de tarefas por execução")
        wf = Workflow(kind=kind, title=title or kind, params=params)
        keys: dict[str, str] = {}
        lim = ExecutionLimits(timeout_s=self.policy.limits.task_timeout_s, max_retries=self.policy.limits.max_retries)
        for key, ttype, deps, inp in plan:
            gate = ttype in APPROVAL_GATES
            task = Task(type=ttype, agent=self.name if gate else TASK_ROUTES[ttype], workflow_id=wf.id,
                        depends_on=[keys[d] for d in deps], input=inp, requires_approval=gate, limits=lim)
            keys[key] = task.id
            wf.task_ids.append(task.id)
            self.store.put("tasks", task)
        self.store.put("workflows", wf)
        self.store.log("info", self.name, f"Workflow {wf.kind} criado com {len(plan)} tarefas: {wf.title}")
        return wf

    # ---------- consultas ----------
    def tasks_of(self, wf: Workflow) -> list[Task]:
        return [t for tid in wf.task_ids if (t := self.store.get("tasks", tid, Task))]

    def _upstream(self, task: Task) -> dict[str, dict[str, Any]]:
        """Saídas de todos os ancestrais concluídos (transitivo), por tipo de tarefa."""
        out: dict[str, dict[str, Any]] = {}
        stack, seen = list(task.depends_on), set()
        while stack:
            tid = stack.pop()
            if tid in seen:
                continue
            seen.add(tid)
            t = self.store.get("tasks", tid, Task)
            if t:
                if t.result:
                    out[t.type] = t.result.output
                stack.extend(t.depends_on)
        return out

    # ---------- execução ----------
    def _ready(self) -> list[Task]:
        ready = []
        for wf in self.store.list("workflows", Workflow):
            if wf.status in TERMINAL:
                continue
            tasks = {t.id: t for t in self.tasks_of(wf)}
            for t in tasks.values():
                if t.status == TaskStatus.pending and t.id not in self._inflight and all(
                    tasks.get(d) and tasks[d].status == TaskStatus.completed for d in t.depends_on
                ):
                    ready.append(t)
        return ready

    def tick(self, sync: bool = False) -> int:
        """Despacha tarefas prontas. Retorna quantas foram iniciadas."""
        started = 0
        for task in self._ready():
            wf = self.store.get("workflows", task.workflow_id, Workflow) if task.workflow_id else None
            if wf and wf.tasks_executed >= self.policy.limits.max_tasks_per_run:
                self._finish(task, TaskStatus.failed, error="Limite de tarefas por execução atingido")
                continue
            if wf and wf.cost_estimated_usd >= self.policy.limits.max_cost_usd_per_run:
                self._finish(task, TaskStatus.cancelled, error="Teto de custo estimado atingido")
                continue
            if task.requires_approval:
                task.status = TaskStatus.awaiting_approval
                self.store.put("tasks", task)
                self.store.log("info", self.name, f"Aguardando aprovação humana: {task.type}", task.id)
                self._refresh(task.workflow_id)
                continue
            with self._lock:
                if len(self._inflight) >= self.policy.limits.max_concurrency and not sync:
                    break
                self._inflight.add(task.id)
            started += 1
            if sync or self._pool is None:
                self._execute(task.id)
            else:
                self._pool.submit(self._execute, task.id)
        return started

    def run_until_idle(self, max_ticks: int = 100) -> None:
        for _ in range(max_ticks):
            if self.tick(sync=True) == 0:
                return

    def _execute(self, task_id: str) -> None:
        try:
            task = self.store.get("tasks", task_id, Task)
            if not task or task.status != TaskStatus.pending:
                return
            agent = AGENTS[task.agent]
            budget = self._budgets.setdefault(task.workflow_id or task.id, ApiBudget(self.policy.limits.max_api_calls_per_run))
            cancel = self._cancel.setdefault(task.id, threading.Event())
            task.status, task.started_at = TaskStatus.running, now()
            task.attempts += 1
            self.store.put("tasks", task)
            self._refresh(task.workflow_id, executed=1)
            self.store.log("info", agent.name, f"Iniciando {task.type} (tentativa {task.attempts})", task.id)
            wf = self.store.get("workflows", task.workflow_id, Workflow) if task.workflow_id else None
            ctx = AgentContext(task, self.store, self.policy, budget, self._upstream(task), agent.owned_kinds, cancel,
                               workflow_params=wf.params if wf else None)
            box: dict[str, Any] = {}

            def target() -> None:
                try:
                    box["result"] = agent.run(task, ctx)
                except BaseException as exc:  # noqa: BLE001 — erro é registrado na tarefa
                    box["error"] = exc

            th = threading.Thread(target=target, daemon=True, name=f"task-{task.id}")
            used_before = budget.used
            th.start()
            th.join(task.limits.timeout_s)
            if th.is_alive():
                cancel.set()  # agentes verificam o sinal; subprocessos têm timeout próprio
                self._fail_or_retry(task, f"Tempo limite de {task.limits.timeout_s}s excedido", retry=False)
                return
            self._add_usage(task.workflow_id, api_calls=budget.used - used_before)
            if "error" in box:
                err = box["error"]
                recoverable = not isinstance(err, (ValueError, PermissionError))
                self._fail_or_retry(task, f"{type(err).__name__}: {err}", retry=recoverable)
                return
            result: TaskResult = box["result"]
            self._add_usage(task.workflow_id, cost=result.cost_estimated_usd, tokens=result.tokens_estimated)
            self._finish(task, TaskStatus.completed if result.ok else TaskStatus.failed, result=result)
            self.store.log("info", agent.name, result.summary, task.id)
        finally:
            with self._lock:
                self._inflight.discard(task_id)
                self._cancel.pop(task_id, None)

    def _fail_or_retry(self, task: Task, error: str, retry: bool) -> None:
        task.errors.append(error)
        self.store.log("error", task.agent, error, task.id)
        if retry and task.attempts <= task.limits.max_retries:
            task.status = TaskStatus.pending
            self.store.put("tasks", task)
            self.store.log("warning", self.name, f"Nova tentativa agendada ({task.attempts}/{task.limits.max_retries + 1})", task.id)
            return
        self._finish(task, TaskStatus.failed)

    def _finish(self, task: Task, status: TaskStatus, result: TaskResult | None = None, error: str | None = None) -> None:
        task.status, task.completed_at = status, now()
        if result:
            task.result = result
        if error:
            task.errors.append(error)
        self.store.put("tasks", task)
        if status in (TaskStatus.failed, TaskStatus.cancelled):
            self._cancel_dependents(task)
        self._refresh(task.workflow_id)

    def _cancel_dependents(self, task: Task) -> None:
        if not task.workflow_id:
            return
        wf = self.store.get("workflows", task.workflow_id, Workflow)
        for t in self.tasks_of(wf):
            if task.id in t.depends_on and t.status not in TERMINAL:
                t.status, t.completed_at = TaskStatus.cancelled, now()
                t.errors.append(f"Cancelada: dependência {task.type} terminou como {task.status.value}")
                self.store.put("tasks", t)
                self._cancel_dependents(t)

    def _add_usage(self, wf_id: str | None, api_calls: int = 0, cost: float = 0.0, tokens: int = 0) -> None:
        if not wf_id:
            return
        with self._lock:
            wf = self.store.get("workflows", wf_id, Workflow)
            if wf:
                wf.api_calls += api_calls
                wf.cost_estimated_usd += cost
                wf.tokens_estimated += tokens
                self.store.put("workflows", wf)

    def _refresh(self, wf_id: str | None, executed: int = 0) -> None:
        if not wf_id:
            return
        with self._lock:
            wf = self.store.get("workflows", wf_id, Workflow)
            if not wf:
                return
            wf.tasks_executed += executed
            states = {t.status for t in self.tasks_of(wf)}
            if states <= TERMINAL:
                wf.status = TaskStatus.failed if TaskStatus.failed in states else (
                    TaskStatus.completed if TaskStatus.completed in states and TaskStatus.cancelled not in states else TaskStatus.cancelled)
                wf.finished_at = wf.finished_at or now()
            elif TaskStatus.awaiting_approval in states:
                wf.status = TaskStatus.awaiting_approval
            elif TaskStatus.running in states or TaskStatus.completed in states:
                wf.status = TaskStatus.running
            self.store.put("workflows", wf)

    # ---------- ações humanas ----------
    def _find(self, task: Task, key: str) -> Any:
        """Procura um identificador nas saídas dos ancestrais e, depois, nos parâmetros do workflow."""
        found = next((o[key] for o in self._upstream(task).values() if key in o), None)
        if found is None and task.workflow_id:
            wf = self.store.get("workflows", task.workflow_id, Workflow)
            found = (wf.params or {}).get(key) if wf else None
        return found

    def approve(self, task_id: str, decided_by: str = "proprietário", note: str = "") -> Task:
        task = self._awaiting(task_id)
        key = APPROVAL_GATES[task.type]
        target_id = self._find(task, key)
        if not target_id:
            raise ApprovalBlocked(f"Não foi possível identificar o {key} desta aprovação")
        reports = [r for r in self.store.list("quality_reports", QualityReport) if r.target_id == target_id]
        if not reports:
            raise ApprovalBlocked("Nenhum relatório de qualidade encontrado")
        if reports[0].blocking:
            fails = [c.label for c in reports[0].checks if c.status == "fail"]
            raise ApprovalBlocked("Bloqueado pelo Quality & Compliance: " + "; ".join(fails))
        if task.type == "editorial_approval":
            script = self.store.get("scripts", target_id, Script)
            script.status = "approved"
            self.store.put("scripts", script)
        task.decided_by = decided_by
        self.store.log("info", self.name, f"Aprovado por {decided_by}. {note}".strip(), task.id)
        self._finish(task, TaskStatus.completed, result=TaskResult(summary=f"Aprovado por {decided_by}", output={"note": note}))
        return task

    def reject(self, task_id: str, decided_by: str = "proprietário", note: str = "") -> Task:
        task = self._awaiting(task_id)
        task.decided_by = decided_by
        if task.type == "editorial_approval":
            sid = self._find(task, "script_id")
            if sid and (script := self.store.get("scripts", sid, Script)):
                script.status = "rejected"
                self.store.put("scripts", script)
        self.store.log("warning", self.name, f"Rejeitado por {decided_by}. {note}".strip(), task.id)
        self._finish(task, TaskStatus.cancelled, result=TaskResult(ok=False, summary=f"Rejeitado: {note}"))
        return task

    def cancel_workflow(self, wf_id: str) -> Workflow:
        wf = self.store.get("workflows", wf_id, Workflow)
        if not wf:
            raise KeyError(wf_id)
        for t in self.tasks_of(wf):
            if t.status == TaskStatus.running and t.id in self._cancel:
                self._cancel[t.id].set()
            if t.status not in TERMINAL:
                t.status, t.completed_at = TaskStatus.cancelled, now()
                self.store.put("tasks", t)
        self._refresh(wf_id)
        return self.store.get("workflows", wf_id, Workflow)

    def retry_task(self, task_id: str) -> Task:
        """Reexecução manual de uma tarefa que falhou (as dependentes canceladas voltam a pendentes)."""
        task = self.store.get("tasks", task_id, Task)
        if not task or task.status != TaskStatus.failed:
            raise ValueError("Só tarefas com falha podem ser repetidas")
        wf = self.store.get("workflows", task.workflow_id, Workflow)
        task.status, task.attempts, task.completed_at = TaskStatus.pending, 0, None
        self.store.put("tasks", task)
        for t in self.tasks_of(wf):
            if t.status == TaskStatus.cancelled:
                t.status, t.completed_at = TaskStatus.pending, None
                self.store.put("tasks", t)
        wf.status, wf.finished_at, wf.tasks_executed = TaskStatus.running, None, 0
        self.store.put("workflows", wf)
        return task

    # A busca visual não é refeita: preserva as validações humanas das cenas.
    REWORK_TYPES = ("retention_review", "fact_review", "editorial_approval", "produce_video", "technical_qa",
                    "final_approval", "publish_prep")

    def rework(self, wf_id: str, decided_by: str = "proprietário") -> Workflow:
        """Destrava o roteiro para edição e refaz revisão → aprovação editorial → render → QA → aprovação final."""
        wf = self.store.get("workflows", wf_id, Workflow)
        if not wf or wf.kind not in ("video", "kitchen_short", "script_short"):
            raise ValueError("Workflow de vídeo não encontrado")
        tasks = self.tasks_of(wf)
        if any(t.status == TaskStatus.running for t in tasks):
            raise ValueError("Aguarde a etapa em execução terminar")
        script_id = next((t.result.output["script_id"] for t in tasks if t.result and "script_id" in t.result.output),
                         (wf.params or {}).get("script_id"))
        if not script_id:
            raise ValueError("Roteiro ainda não foi gerado")
        script = self.store.get("scripts", script_id, Script)
        script.status = "draft"
        self.store.put("scripts", script)
        for t in tasks:
            if t.type in self.REWORK_TYPES:
                t.status, t.result, t.errors, t.attempts = TaskStatus.pending, None, [], 0
                t.started_at = t.completed_at = t.decided_by = None
                self.store.put("tasks", t)
        wf.status, wf.finished_at, wf.tasks_executed = TaskStatus.running, None, 0
        self.store.put("workflows", wf)
        self.store.log("info", self.name, f"Refazer solicitado por {decided_by}: roteiro destravado para edição", None)
        return wf

    def approval_context(self, task_id: str) -> dict[str, Any]:
        """Tudo o que um humano precisa ver antes de decidir: roteiro, vídeo e relatórios de qualidade."""
        task = self.store.get("tasks", task_id, Task)
        if not task:
            raise ValueError("Tarefa não encontrada")
        script_id, job_id = self._find(task, "script_id"), self._find(task, "job_id")
        reports = self.store.list("quality_reports", QualityReport)
        latest = lambda tid: next((r for r in reports if r.target_id == tid), None)  # noqa: E731
        from ..models import ProductionJob  # import local: evita ciclo no carregamento

        return {
            "task": task,
            "workflow": self.store.get("workflows", task.workflow_id, Workflow) if task.workflow_id else None,
            "script": self.store.get("scripts", script_id, Script) if script_id else None,
            "script_quality": latest(script_id) if script_id else None,
            "job": self.store.get("jobs", job_id, ProductionJob) if job_id else None,
            "job_quality": latest(job_id) if job_id else None,
        }

    def _awaiting(self, task_id: str) -> Task:
        task = self.store.get("tasks", task_id, Task)
        if not task or task.status != TaskStatus.awaiting_approval or task.type not in APPROVAL_GATES:
            raise ValueError("Tarefa não está aguardando aprovação")
        return task

    def run_adhoc(self, task_type: str, inp: dict[str, Any]) -> TaskResult:
        """Execução avulsa e síncrona de uma tarefa rápida (ex.: revisar roteiro após edição)."""
        agent = AGENTS[TASK_ROUTES[task_type]]
        task = Task(type=task_type, agent=agent.name, input=inp)
        ctx = AgentContext(task, self.store, self.policy, ApiBudget(self.policy.limits.max_api_calls_per_run), {}, agent.owned_kinds)
        result = agent.run(task, ctx)
        task.status, task.result, task.completed_at, task.attempts = TaskStatus.completed, result, now(), 1
        self.store.put("tasks", task)
        return result

    # ---------- runner ----------
    def start(self) -> None:
        if self._runner and self._runner.is_alive():
            return
        self._recover()
        self._stop.clear()
        self._pool = ThreadPoolExecutor(max_workers=self.policy.limits.max_concurrency, thread_name_prefix="agent")
        self._runner = threading.Thread(target=self._loop, daemon=True, name="orchestrator")
        self._runner.start()

    def stop(self) -> None:
        self._stop.set()
        for ev in list(self._cancel.values()):
            ev.set()
        if self._runner:
            self._runner.join(timeout=5)
        if self._pool:
            self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as exc:  # o loop nunca morre silenciosamente
                self.store.log("error", self.name, f"Falha no ciclo do orquestrador: {exc}")
            self._stop.wait(1.0)

    def _recover(self) -> None:
        """Tarefas 'running' de uma execução anterior interrompida voltam a 'failed' (sem órfãos)."""
        for t in self.store.list("tasks", Task, limit=500):
            if t.status == TaskStatus.running:
                t.errors.append("Interrompida por reinício do servidor")
                self._finish(t, TaskStatus.failed)


_orch: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orch
    if _orch is None:
        _orch = Orchestrator()
    return _orch


def reset_orchestrator() -> None:
    global _orch
    if _orch:
        _orch.stop()
    _orch = None


def wait_idle(orch: Orchestrator, timeout_s: float = 30) -> None:
    end = time.time() + timeout_s
    while time.time() < end and orch._inflight:
        time.sleep(0.1)
