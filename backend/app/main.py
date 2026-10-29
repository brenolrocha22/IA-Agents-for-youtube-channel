"""Ponto de entrada: `uvicorn app.main:app` a partir de backend/."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.kitchen import router as kitchen_router
from .api.routes import router
from .api.visual import router as visual_router
from .config import ROOT, output_dir
from .orchestrator.orchestrator import get_orchestrator

DIST = ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    orch = get_orchestrator()
    orch.start()
    yield
    orch.stop()


app = FastAPI(title="Creator Intelligence OS", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
app.include_router(kitchen_router)
app.include_router(visual_router)
app.mount("/media", StaticFiles(directory=output_dir()), name="media")

if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        target = (DIST / path).resolve()
        if path and target.is_file() and target.is_relative_to(DIST.resolve()):
            return FileResponse(target)
        return FileResponse(DIST / "index.html")
