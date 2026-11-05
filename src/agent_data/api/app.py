"""Application FastAPI : sert le front web de demonstration.

Le code genere par le LLM ne s'execute toujours que dans le sandbox Docker : l'API ne
fait qu'orchestrer. Comme elle peut etre exposee sur Internet pour une demo, elle est
protegee par un jeton et ne sert que les jeux de donnees connus de `data/` — jamais un
chemin fourni par le client.
"""

from __future__ import annotations

import asyncio
import hmac
import json
from collections.abc import AsyncIterator
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent_data.api.runs import RunBusyError, RunManager
from agent_data.config import DATA_DIR, Role, Settings, get_settings
from agent_data.eval.cases import CASES
from agent_data.gpu import gpu_info, read_sample
from agent_data.gpu_catalog import comparison
from agent_data.llm import OllamaClient
from agent_data.profiling import profile_csv
from agent_data.sandbox import DockerSandbox, docker_available

ROLES: tuple[Role, ...] = ("planner", "coder", "critic", "synthesis")


class RunRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    datasets: list[str] = Field(min_length=1, max_length=3)
    validate_plan: bool = True


class Approval(BaseModel):
    approved: bool


def _dataset_csvs(data_dir: Path) -> dict[str, Path]:
    """Jeux de donnees servis : un CSV par sous-dossier de `data/`."""
    if not data_dir.exists():
        return {}
    found = {}
    for folder in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        csv = next(iter(sorted(folder.glob("*.csv"))), None)
        if csv is not None:
            found[folder.name] = csv
    return found


def create_app(
    *,
    settings: Settings | None = None,
    manager: RunManager | None = None,
    data_dir: Path = DATA_DIR,
) -> FastAPI:
    settings = settings or get_settings()
    manager = manager or RunManager()
    app = FastAPI(title="Agent Data", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.api_cors_origins.split(",") if o.strip()],
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    def require_token(authorization: str = Header(default="")) -> None:
        if not settings.api_token:
            return  # developpement local : pas de jeton configure
        supplied = authorization.removeprefix("Bearer ").strip()
        if not hmac.compare_digest(supplied, settings.api_token):
            raise HTTPException(status_code=401, detail="Jeton invalide ou absent.")

    auth = [Depends(require_token)]

    @lru_cache(maxsize=16)
    def _profile(name: str):
        return profile_csv(_dataset_csvs(data_dir)[name], name=name)

    @app.get("/api/health")
    def health() -> dict:
        """Etat des prerequis. Public : ne revele que des booleens et des noms de modeles."""
        ollama = OllamaClient(settings)
        llm_ok = ollama.is_available()
        installed = ollama.installed_models() if llm_ok else []
        docker_ok = docker_available()
        models = {role: settings.model_for(role) for role in ROLES}
        return {
            "llm": llm_ok,
            "docker": docker_ok,
            "sandbox_image": docker_ok and DockerSandbox(settings).image_exists(),
            "models": {
                role: {"name": name, "installed": name in installed}
                for role, name in models.items()
            },
            "auth_required": bool(settings.api_token),
            "busy": manager.active is not None,
        }

    @app.get("/api/system", dependencies=auth)
    def system() -> dict:
        """Materiel qui porte l'agent : GPU detecte, mesure en direct, comparaison."""
        info = gpu_info()
        sample = read_sample()
        sizes = OllamaClient(settings).model_sizes_gb()
        used = {settings.model_for(role) for role in ROLES}
        return {
            "gpu": info.as_dict() if info else None,
            "live": (
                {
                    "memory_used_mb": sample.memory_used_mb,
                    "power_w": sample.power_w,
                    "utilization_pct": sample.utilization_pct,
                }
                if sample
                else None
            ),
            "models": [
                {"name": m, "size_gb": round(sizes[m], 1)} for m in sorted(used) if m in sizes
            ],
            "catalog": comparison({m: sizes[m] for m in used if m in sizes}),
        }

    @app.get("/api/datasets", dependencies=auth)
    def datasets() -> list[dict]:
        questions: dict[str, list[str]] = {}
        for case in CASES:
            questions.setdefault(case.dataset, []).append(case.question)
        out = []
        for name in _dataset_csvs(data_dir):
            profile = _profile(name)
            out.append(
                {
                    "name": name,
                    "rows": profile.row_count,
                    "columns": [
                        {"name": c.name, "kind": c.kind.value, "unique": c.unique_count}
                        for c in profile.columns
                    ],
                    "questions": questions.get(name, []),
                }
            )
        return out

    @app.post("/api/runs", dependencies=auth)
    def start_run(body: RunRequest) -> dict:
        known = _dataset_csvs(data_dir)
        unknown = [d for d in body.datasets if d not in known]
        if unknown:
            raise HTTPException(404, f"Jeu(x) de donnees inconnu(s) : {', '.join(unknown)}")
        try:
            run = manager.start(
                body.question,
                {d: known[d] for d in body.datasets},
                validate_plan=body.validate_plan,
            )
        except RunBusyError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"run_id": run.id}

    @app.get("/api/runs/{run_id}/events", dependencies=auth)
    async def run_events(run_id: str, after: int = Query(default=0, ge=0)) -> StreamingResponse:
        run = manager.get(run_id)
        if run is None:
            raise HTTPException(404, "Run inconnu.")

        async def stream() -> AsyncIterator[str]:
            cursor = after
            while True:
                batch = run.events_after(cursor)
                for event in batch:
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                cursor += len(batch)
                if run.finished and not run.events_after(cursor):
                    return
                if not batch:
                    yield ": keep-alive\n\n"
                await asyncio.sleep(0.3)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/runs/{run_id}/approval", dependencies=auth)
    def approve(run_id: str, body: Approval) -> dict:
        run = manager.get(run_id)
        if run is None:
            raise HTTPException(404, "Run inconnu.")
        run.decide(body.approved)
        return {"ok": True}

    return app
