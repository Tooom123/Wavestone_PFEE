"""Suivi des garde-fous dans le temps : un journal JSONL, une ligne par run.

Chaque run note ses declenchements de garde-fous (`RunTrace.block`) dans l'ordre. Le
journal permet de repondre aux questions du suivi : quel agent bloque le plus, quels
enchainements menent a un echec, combien de questions sont hors perimetre.

Le journal ne contient ni donnees ni question : un run y est decrit par ses jeux de
donnees, son issue et ses garde-fous. Il reste sur le poste (`.agent_data/`, non versionne).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_data.schemas import AgentState

OUTCOMES = {
    "repondu": "réponse produite",
    "hors_perimetre": "question hors périmètre, aucun calcul",
    "plafond": "plafond d'itérations atteint",
    "refuse": "plan refusé par l'utilisateur",
    "erreur": "erreur technique",
}


def outcome(state: AgentState | None, guardrails: list[dict[str, str]]) -> str:
    """Issue d'un run, deduite de son etat final et de ses garde-fous."""
    names = {g["name"] for g in guardrails}
    if state is None:
        return "erreur"
    if "hors_perimetre" in names:
        return "hors_perimetre"
    if "plan_refuse" in names:
        return "refuse"
    if "plafond_iterations" in names:
        return "plafond"
    return "repondu"


def record(path: Path, *, run_id: str, datasets: list[str], state: AgentState | None,
           guardrails: list[dict[str, str]], seconds: float) -> dict[str, Any]:  # fmt: skip
    """Ajoute un run au journal et rend la ligne ecrite."""
    entry = {
        "at": datetime.now().isoformat(timespec="seconds"),
        "run": run_id,
        "datasets": datasets,
        "outcome": outcome(state, guardrails),
        "iterations": state.iteration if state else 0,
        "seconds": round(seconds, 1),
        "guardrails": [{"agent": g["agent"], "name": g["name"]} for g in guardrails],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


@dataclass
class Summary:
    runs: int = 0
    outcomes: Counter[str] = field(default_factory=Counter)
    by_agent: Counter[str] = field(default_factory=Counter)
    by_guardrail: Counter[tuple[str, str]] = field(default_factory=Counter)
    flows: Counter[str] = field(default_factory=Counter)

    def render(self) -> str:
        if not self.runs:
            return "Aucun run enregistre."
        lines = [f"{self.runs} run(s)", "", "Issues :"]
        lines += [f"  {n:>4}  {OUTCOMES.get(k, k)}" for k, n in self.outcomes.most_common()]
        lines += ["", "Declenchements par agent :"]
        lines += [f"  {n:>4}  {agent}" for agent, n in self.by_agent.most_common()]
        lines += ["", "Par garde-fou :"]
        lines += [f"  {n:>4}  {a} / {g}" for (a, g), n in self.by_guardrail.most_common()]
        if self.flows:
            lines += ["", "Enchainements les plus frequents (runs sans reponse acceptee) :"]
            lines += [f"  {n:>4}  {flow}" for flow, n in self.flows.most_common(5)]
        return "\n".join(lines)


def summarize(path: Path) -> Summary:
    """Agrege le journal : issues, declenchements par agent, enchainements menant a un echec."""
    summary = Summary()
    if not path.exists():
        return summary
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        summary.runs += 1
        summary.outcomes[entry["outcome"]] += 1
        for g in entry["guardrails"]:
            summary.by_agent[g["agent"]] += 1
            summary.by_guardrail[(g["agent"], g["name"])] += 1
        if entry["outcome"] != "repondu" and entry["guardrails"]:
            summary.flows[" > ".join(_dedupe(entry["guardrails"]))] += 1
    return summary


def _dedupe(guardrails: list[dict[str, str]]) -> list[str]:
    """« coder:code_en_erreur > coder:code_en_erreur » devient « coder:code_en_erreur x2 »."""
    steps: list[list[Any]] = []
    for g in guardrails:
        label = f"{g['agent']}:{g['name']}"
        if steps and steps[-1][0] == label:
            steps[-1][1] += 1
        else:
            steps.append([label, 1])
    return [label if n == 1 else f"{label} x{n}" for label, n in steps]
