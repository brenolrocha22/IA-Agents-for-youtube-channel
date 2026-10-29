"""Contrato dos agentes. Agentes só leem/gravam documentos dos tipos que possuem e nunca alteram tarefas."""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Any, ClassVar, TypeVar

from pydantic import BaseModel

from ..config import Policy
from ..models import Task, TaskResult
from ..research.http import ApiBudget
from ..store import Store

M = TypeVar("M", bound=BaseModel)


class Cancelled(RuntimeError):
    pass


class AgentContext:
    def __init__(
        self,
        task: Task,
        store: Store,
        policy: Policy,
        budget: ApiBudget,
        upstream: dict[str, dict[str, Any]],
        owned_kinds: frozenset[str],
        cancel_event: threading.Event | None = None,
        workflow_params: dict[str, Any] | None = None,
    ):
        self.workflow_params = workflow_params or {}
        self.task = task
        self.store = store
        self.policy = policy  # imutável (frozen)
        self.budget = budget
        self.upstream = upstream  # saídas das tarefas das quais esta depende, por tipo de tarefa
        self._owned = owned_kinds
        self._cancel = cancel_event or threading.Event()

    def log(self, message: str, level: str = "info") -> None:
        self.store.log(level, self.task.agent, message, self.task.id)

    def read(self, kind: str, doc_id: str, cls: type[M]) -> M | None:
        return self.store.get(kind, doc_id, cls)

    def save(self, kind: str, doc: BaseModel) -> None:
        if kind not in self._owned:
            raise PermissionError(f"Agente {self.task.agent} não pode gravar documentos do tipo '{kind}'")
        self.store.put(kind, doc)

    def check_cancelled(self) -> None:
        if self._cancel.is_set():
            raise Cancelled("Tarefa cancelada ou tempo limite atingido")

    def param(self, key: str, default: Any = None) -> Any:
        """Busca na entrada da tarefa, nas saídas das dependências e, por fim, nos parâmetros do workflow."""
        if key in self.task.input:
            return self.task.input[key]
        for out in self.upstream.values():
            if key in out:
                return out[key]
        return self.workflow_params.get(key, default)


class Agent(ABC):
    name: ClassVar[str]
    title: ClassVar[str]
    description: ClassVar[str]
    task_types: ClassVar[tuple[str, ...]]
    owned_kinds: ClassVar[frozenset[str]] = frozenset()

    @abstractmethod
    def run(self, task: Task, ctx: AgentContext) -> TaskResult: ...
