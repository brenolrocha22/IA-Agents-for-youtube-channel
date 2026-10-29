from fastapi.testclient import TestClient

from app.main import app
from app.models import VisualPlan, VisualScene
from app.production import ffmpeg
from app.store import get_store


def _plan() -> VisualPlan:
    plan = VisualPlan(script_id="s_up", subject_en="octopus", providers=[],
                      scenes=[VisualScene(index=0, narration="O polvo solta tinta.", action="ink", queries=[])])
    get_store().put("visual_plans", plan)
    return plan


def test_upload_licensed_footage(tmp_path):
    clip = tmp_path / "ink.mp4"
    ffmpeg.run(["-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=3", "-pix_fmt", "yuv420p", str(clip)], 60)
    plan = _plan()
    with TestClient(app) as c:
        data = {"page_url": "https://www.pexels.com/pt-br/video/polvo-123/", "author": "Fulano", "license": "Pexels License"}
        r = c.post(f"/api/visual/plans/{plan.id}/scenes/0/upload", data=data, files={"file": ("ink.mp4", clip.read_bytes(), "video/mp4")})
        assert r.status_code == 200, r.text
        scene = r.json()["plan"]["scenes"][0]
        cand = scene["candidates"][0]
        assert scene["selected_id"] == cand["id"] and scene["validation"] == "revisao"  # ainda exige validação visual
        assert cand["provider"] == "Pexels" and cand["license_status"] == "aceita" and cand["preview_path"]
        # licença fora da lista e autorização sem descrição são recusadas
        bad = c.post(f"/api/visual/plans/{plan.id}/scenes/0/upload", data={**data, "license": "Instagram"},
                     files={"file": ("ink.mp4", clip.read_bytes(), "video/mp4")})
        assert bad.status_code == 422
        bad = c.post(f"/api/visual/plans/{plan.id}/scenes/0/upload", data={**data, "license": "Autorização do autor"},
                     files={"file": ("ink.mp4", clip.read_bytes(), "video/mp4")})
        assert bad.status_code == 422
        not_video = c.post(f"/api/visual/plans/{plan.id}/scenes/0/upload", data=data, files={"file": ("x.txt", b"oi", "text/plain")})
        assert not_video.status_code == 415
