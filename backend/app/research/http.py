"""GET JSON com cache em SQLite e orçamento de chamadas por execução."""
from __future__ import annotations

import hashlib
import json
import threading
from typing import Any

import httpx

from ..config import wikimedia_user_agent
from ..store import Store


class LimitExceeded(RuntimeError):
    pass


class ApiBudget:
    def __init__(self, max_calls: int):
        self.max_calls = max_calls
        self.used = 0
        self._lock = threading.Lock()

    def consume(self, n: int = 1) -> None:
        with self._lock:
            if self.used + n > self.max_calls:
                raise LimitExceeded(f"Limite de {self.max_calls} chamadas de API por execução atingido")
            self.used += n


class NotFound(Exception):
    pass


def get_json(
    url: str,
    *,
    store: Store,
    ttl_s: int,
    budget: ApiBudget | None = None,
    params: dict[str, Any] | None = None,
    redact_params: tuple[str, ...] = ("key",),
    timeout_s: float = 20.0,
) -> Any:
    """Retorna JSON (do cache se válido). Lança NotFound em 404. Chaves nunca entram na chave de cache."""
    safe_params = {k: v for k, v in (params or {}).items() if k not in redact_params}
    key = hashlib.sha256((url + json.dumps(safe_params, sort_keys=True)).encode()).hexdigest()
    cached = store.cache_get(key)
    if cached is not None:
        if cached == {"__not_found__": True}:
            raise NotFound(url)
        return cached
    if budget:
        budget.consume()
    headers = {"User-Agent": wikimedia_user_agent(), "Accept": "application/json"}
    resp = httpx.get(url, params=params, headers=headers, timeout=timeout_s, follow_redirects=True)
    if resp.status_code == 404:
        store.cache_set(key, {"__not_found__": True}, ttl_s)
        raise NotFound(url)
    resp.raise_for_status()
    data = resp.json()
    store.cache_set(key, data, ttl_s)
    return data
