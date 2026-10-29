from fastapi.testclient import TestClient

from app.main import app


def test_health_settings_and_no_secret_leak(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "segredo-super-123")
    with TestClient(app) as c:
        assert c.get("/api/health").json()["status"] == "ok"
        r = c.get("/api/settings")
        assert r.status_code == 200
        assert "segredo-super-123" not in r.text
        yt = next(e for e in r.json()["env"] if e["name"] == "YOUTUBE_API_KEY")
        assert yt["configured"] and "value" not in yt
        assert c.get("/api/dashboard").status_code == 200
        assert c.get("/api/agents").status_code == 200
        assert len(c.get("/api/agents").json()) == 10  # orquestrador + 7 agentes base + Reality Kitchen + Visual Hunter


def test_channels_and_branding():
    with TestClient(app) as c:
        chs = c.get("/api/channels").json()
        assert {ch["id"] for ch in chs} == {"clips_plus", "natureza"}
        out = c.post("/api/channels/clips_plus/branding").json()["branding"]
        assert {"avatar_800x800", "banner_2560x1440", "capa_modelo_1080x1920"} <= set(out)


def test_approve_unknown_task_is_400():
    with TestClient(app) as c:
        assert c.post("/api/tasks/nao_existe/approve", json={"note": ""}).status_code == 400


def test_analytics_demo_is_flagged():
    with TestClient(app) as c:
        rep = c.get("/api/analytics", params={"demo": True}).json()
        assert rep["report"]["demo"] is True
        real = c.get("/api/analytics").json()
        assert real["report"]["demo"] is False and real["report"]["records"] == 0
