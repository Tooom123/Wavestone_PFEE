"""Gestion des runs de l'agent cote API.

Un run tourne dans un thread (le LLM local et le sandbox sont bloquants) et publie ses
evenements dans un journal que le front relit par streaming. Un seul run a la fois : le
modele occupe la carte graphique, deux runs concurrents se disputeraient la VRAM.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from agent_data import monitoring
from agent_data.gpu import GpuSampler
from agent_data.graph import RunTrace, Stage1
from agent_data.pipeline import analyze
from agent_data.sandbox import SandboxUnavailableError

#: Delai laisse a l'utilisateur pour valider le plan avant d'abandonner le run.
APPROVAL_TIMEOUT_SECONDS = 600


class RunBusyError(RuntimeError):
    """Un autre run occupe deja la machine."""


@dataclass
class Run:
    """Etat d'un run : journal d'evenements, validation du plan, resultat."""

    id: str
    question: str
    datasets: list[str]
    events: list[dict] = field(default_factory=list)
    finished: bool = False
    started_at: float = field(default_factory=time.time)
    approval_wait_seconds: float = 0.0
    """Temps passe a attendre la validation humaine : de l'attente, pas du calcul."""
    _approval: threading.Event = field(default_factory=threading.Event)
    _approved: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def publish(self, event: dict) -> None:
        with self._lock:
            self.events.append({**event, "i": len(self.events), "t": round(time.time(), 2)})

    def events_after(self, index: int) -> list[dict]:
        with self._lock:
            return self.events[index:]

    def decide(self, approved: bool) -> None:
        self._approved = approved
        self._approval.set()

    def wait_for_approval(self) -> bool:
        """Bloque le run jusqu'a la decision de l'utilisateur."""
        started = time.time()
        decided = self._approval.wait(timeout=APPROVAL_TIMEOUT_SECONDS)
        self.approval_wait_seconds = time.time() - started
        return decided and self._approved


class RunManager:
    """Lance les runs et les retrouve par identifiant."""

    def __init__(self, stage1_factory=Stage1) -> None:
        self._stage1_factory = stage1_factory
        self._runs: dict[str, Run] = {}
        self._busy = threading.Lock()

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    @property
    def active(self) -> Run | None:
        return next((r for r in self._runs.values() if not r.finished), None)

    def start(self, question: str, csvs: dict[str, Path], *, validate_plan: bool) -> Run:
        if not self._busy.acquire(blocking=False):
            raise RunBusyError("Un run est deja en cours : attendre sa fin.")
        run = Run(id=uuid.uuid4().hex[:12], question=question, datasets=list(csvs))
        self._runs[run.id] = run
        threading.Thread(target=self._execute, args=(run, csvs, validate_plan), daemon=True).start()
        return run

    def _execute(self, run: Run, csvs: dict[str, Path], validate_plan: bool) -> None:
        try:
            stage1 = self._stage1_factory()
            # La validation se decide par run (case a cocher du front), pas globalement.
            stage1.settings = stage1.settings.model_copy(update={"human_validation": validate_plan})
            trace = RunTrace(listener=run.publish)
            run.publish({"kind": "start", "question": run.question, "datasets": run.datasets})

            sampler = GpuSampler()
            sampler.start()
            state = None
            try:
                report, state = analyze(
                    run.question,
                    list(csvs.values()),
                    stage1=stage1,
                    approve_plan=lambda _state: run.wait_for_approval(),
                    trace=trace,
                )
            finally:
                gpu = sampler.stop()
                if stage1.settings.guardrail_log:
                    monitoring.record(
                        Path(stage1.settings.guardrail_log),
                        run_id=run.id,
                        datasets=run.datasets,
                        state=state,
                        guardrails=trace.guardrails,
                        seconds=time.time() - run.started_at,
                    )
            run.publish(
                {
                    "kind": "done",
                    "report": report.to_dict(),
                    "code": state.code,
                    "iterations": state.iteration,
                    "errors": state.errors,
                    "metrics": {
                        "usage": stage1.usage_by_role(),
                        "models": {r: stage1.settings.model_for(r) for r in stage1.clients},
                        "approval_wait_seconds": round(run.approval_wait_seconds, 1),
                        "gpu": gpu.as_dict(),
                        "wall_seconds": round(time.time() - run.started_at, 1),
                        "guardrails": trace.guardrails,
                        "guardrail_counts": trace.guardrail_counts(),
                    },
                }
            )
        except SandboxUnavailableError as exc:
            run.publish({"kind": "error", "message": str(exc), "fatal": "sandbox"})
        except Exception as exc:  # noqa: BLE001 - tout echec doit remonter au front
            run.publish({"kind": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            run.finished = True
            self._busy.release()
