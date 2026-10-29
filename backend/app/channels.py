"""Perfis de canal (config/channels.json)."""
from __future__ import annotations

from typing import Any

from .config import load_json

DEFAULT_BY_WORKFLOW = {"kitchen_short": "clips_plus", "video": "natureza"}


def channels() -> list[dict[str, Any]]:
    return load_json("channels.json")["channels"]


def get_channel(channel_id: str | None, workflow_kind: str = "video") -> dict[str, Any]:
    items = channels()
    wanted = channel_id or DEFAULT_BY_WORKFLOW.get(workflow_kind, items[0]["id"])
    return next((c for c in items if c["id"] == wanted), items[0])


def palette(channel: dict[str, Any]) -> tuple[tuple[int, ...], ...]:
    p = channel["palette"]
    return tuple(p["top"]), tuple(p["bottom"]), tuple(p["accent"]), tuple(p["accent2"])
