"""Configuração: caminhos, variáveis de ambiente e política (somente leitura)."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

CONFIG_DIR = ROOT / "config"


def data_dir() -> Path:
    path = Path(os.getenv("CIOS_DATA_DIR", ROOT / "data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def output_dir() -> Path:
    path = Path(os.getenv("CIOS_OUTPUT_DIR", ROOT / "output"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_json(name: str) -> dict[str, Any]:
    return json.loads((CONFIG_DIR / name).read_text(encoding="utf-8"))


class Limits(BaseModel):
    model_config = ConfigDict(frozen=True)
    task_timeout_s: int
    max_retries: int
    max_concurrency: int
    max_tasks_per_run: int
    max_file_size_mb: int
    max_api_calls_per_run: int
    max_cost_usd_per_run: float
    max_render_seconds: int
    max_video_duration_s: int
    max_short_duration_s: int = 60


class Policy(BaseModel):
    """Imutável: agentes e orquestrador recebem esta instância, mas não podem alterá-la."""

    model_config = ConfigDict(frozen=True)
    auto_allowed: tuple[str, ...]
    requires_human_approval: tuple[str, ...]
    allowed_subprocesses: tuple[str, ...]
    allowed_write_dirs: tuple[str, ...]
    limits: Limits


@lru_cache
def get_policy() -> Policy:
    raw = load_json("policy.json")
    raw.pop("_doc", None)
    return Policy.model_validate(raw)


# Variáveis conhecidas. A API só informa se estão configuradas, nunca o valor.
ENV_VARS: dict[str, dict[str, Any]] = {
    "WIKIMEDIA_USER_AGENT": {"secret": False, "used_by": "Pesquisa (Wikimedia)"},
    "YOUTUBE_API_KEY": {"secret": True, "used_by": "Concorrência (YouTube Data API v3)"},
    "PEXELS_API_KEY": {"secret": True, "used_by": "Visual Hunter (filmagens Pexels)"},
    "PIXABAY_API_KEY": {"secret": True, "used_by": "Visual Hunter (filmagens Pixabay)"},
    "SCRIPT_PROVIDER": {"secret": False, "used_by": "Roteiros"},
    "ANTHROPIC_API_KEY": {"secret": True, "used_by": "Reservado (não usado)"},
    "OPENAI_API_KEY": {"secret": True, "used_by": "ChatGPT: revisão de roteiro, storytelling e copywriting"},
    "OPENAI_MODEL": {"secret": False, "used_by": "Modelo do ChatGPT (nome exato da sua conta)"},
    "FFMPEG_PATH": {"secret": False, "used_by": "Renderização"},
    "TTS_PROVIDER": {"secret": False, "used_by": "Narração"},
    "TTS_VOICE_PT": {"secret": False, "used_by": "Narração pt-BR"},
    "TTS_VOICE_EN": {"secret": False, "used_by": "Narração en"},
    "YOUTUBE_OAUTH_CLIENT_ID": {"secret": True, "used_by": "Publicação (desativada)"},
    "YOUTUBE_OAUTH_CLIENT_SECRET": {"secret": True, "used_by": "Publicação (desativada)"},
}


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def env_status() -> list[dict[str, Any]]:
    out = []
    for name, meta in ENV_VARS.items():
        value = env(name)
        item = {"name": name, "configured": bool(value), "secret": meta["secret"], "used_by": meta["used_by"]}
        if not meta["secret"] and value:
            item["value"] = value
        out.append(item)
    return out


def wikimedia_user_agent() -> str:
    # Política da Wikimedia: "<cliente>/<versão> (<contato>) <biblioteca>/<versão>". Defina um contato real no .env.
    return env("WIKIMEDIA_USER_AGENT") or "CreatorIntelligenceOS/0.1 (local research tool; https://localhost) httpx/0.28"
