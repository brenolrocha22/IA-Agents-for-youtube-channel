"""Provedor LLM opcional (modo híbrido): OpenAI/ChatGPT para revisão de roteiro, storytelling e copywriting.

Desativado sem OPENAI_API_KEY e OPENAI_MODEL (o nome do modelo é o que aparece na conta do proprietário).
Custos: tokens reais vêm da resposta; preço por 1M tokens é configurável (OPENAI_PRICE_IN/OUT_PER_1M).
O LLM nunca é fonte de fatos: o texto gerado passa pelas mesmas verificações do Quality & Compliance.
"""
from __future__ import annotations

import json

import httpx

from ..config import env

API = "https://api.openai.com/v1/chat/completions"
MAX_TOKENS_PER_CALL = 2500


class LLMNotConfigured(RuntimeError):
    pass


class OpenAIProvider:
    name = "openai"

    def is_configured(self) -> bool:
        return bool(env("OPENAI_API_KEY") and env("OPENAI_MODEL"))

    def model(self) -> str:
        return env("OPENAI_MODEL")

    def cost(self, usage: dict) -> float:
        try:
            pin, pout = float(env("OPENAI_PRICE_IN_PER_1M", "0")), float(env("OPENAI_PRICE_OUT_PER_1M", "0"))
        except ValueError:
            return 0.0
        return round(usage.get("prompt_tokens", 0) / 1e6 * pin + usage.get("completion_tokens", 0) / 1e6 * pout, 5)

    def chat_json(self, system: str, user: str, timeout_s: int = 90) -> tuple[dict, dict]:
        """Retorna (objeto JSON, uso com tokens e custo estimado)."""
        if not self.is_configured():
            raise LLMNotConfigured("Configure OPENAI_API_KEY e OPENAI_MODEL no .env para usar o ChatGPT")
        r = httpx.post(API, timeout=timeout_s, headers={"Authorization": f"Bearer {env('OPENAI_API_KEY')}"}, json={
            "model": self.model(), "response_format": {"type": "json_object"}, "max_completion_tokens": MAX_TOKENS_PER_CALL,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        })
        if r.status_code >= 400:  # nunca inclui a chave na mensagem
            raise RuntimeError(f"OpenAI respondeu {r.status_code}: {r.text[:300]}")
        data = r.json()
        usage = data.get("usage", {})
        usage = {"prompt_tokens": usage.get("prompt_tokens", 0), "completion_tokens": usage.get("completion_tokens", 0),
                 "total_tokens": usage.get("total_tokens", 0)}
        usage["cost_usd"] = self.cost(usage)
        return json.loads(data["choices"][0]["message"]["content"]), usage


def get_llm() -> OpenAIProvider | None:
    p = OpenAIProvider()
    return p if p.is_configured() else None
