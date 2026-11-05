"""Enchainement des deux etages.

Les deux etages restent utilisables separement — c'est le decoupage demande par Wavestone.
Cette fonction ne fait que les relier, via le contrat d'artefacts.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from agent_data.graph import PlanApproval, RunTrace, Stage1
from agent_data.rendering import Report, synthesize
from agent_data.schemas import AgentState


def analyze(
    question: str,
    csv_paths: Sequence[Path | str],
    *,
    stage1: Stage1 | None = None,
    approve_plan: PlanApproval | None = None,
    trace: RunTrace | None = None,
) -> tuple[Report, AgentState]:
    """Execute l'analyse de bout en bout et retourne le rapport et l'etat final."""
    stage1 = stage1 or Stage1()
    state = stage1.run(question, csv_paths, approve_plan=approve_plan, trace=trace)

    if state.plan is None:
        raise RuntimeError("Aucun plan n'a pu etre produit pour cette question.")

    if trace is not None:
        trace.emit("stage", name="synthesis", model=stage1.settings.model_for("synthesis"))
    synthesis = synthesize(state.plan, state.artifacts, client=stage1.clients["synthesis"])
    return Report.build(state.plan, state.artifacts, synthesis), state
