"""Verrou des modeles : quelle version exacte de chaque modele sert chaque agent.

Un nom Ollama (`qwen2.5-coder:14b`) n'identifie pas une version : `ollama pull` peut
remplacer le modele par une revision publiee sous le meme nom, et les reponses de l'agent
changent sans que rien ne l'ait signale. Le verrou (`models.lock.json`, versionne) enregistre
le condensat (`digest`) de chaque modele et le score du golden dataset obtenu avec eux.

Trois usages :
- `agent-data modeles verifier` : le poste sert-il les modeles figes ? (et `agent-data check`)
- `agent-data modeles figer` : enregistre les modeles actuels, apres une evaluation ;
- `scripts/upgrade_model.py` : un nouveau modele ne remplace l'ancien que si le golden
  dataset ne regresse pas.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from agent_data.config import PROJECT_ROOT, ROLES, Settings

LOCK_PATH = PROJECT_ROOT / "models.lock.json"


@dataclass(frozen=True)
class Drift:
    role: str
    kind: str  # "modele_change" | "version_changee" | "absent" | "non_fige"
    message: str


def snapshot(settings: Settings, tags: list[dict], overrides: dict[str, str] | None = None) -> dict:
    """Le modele de chaque role, avec son condensat et ses caracteristiques."""
    by_name = {t.get("name", ""): t for t in tags}
    roles: dict[str, dict[str, Any]] = {}
    for role in ROLES:
        name = (overrides or {}).get(role) or settings.model_for(role)
        tag = by_name.get(name, {})
        details = tag.get("details", {})
        roles[role] = {
            "model": name,
            "digest": tag.get("digest", ""),
            "parameters": details.get("parameter_size", ""),
            "quantization": details.get("quantization_level", ""),
        }
    return roles


def check(lock: dict | None, settings: Settings, tags: list[dict]) -> list[Drift]:
    """Ecarts entre le verrou et ce que le poste sert reellement."""
    if lock is None:
        return [Drift("*", "non_fige", "aucun verrou : lancer « agent-data modeles figer »")]
    current = snapshot(settings, tags)
    drifts = []
    for role in ROLES:
        locked, now = lock["roles"].get(role, {}), current[role]
        if not now["digest"]:
            drifts.append(Drift(role, "absent", f"{now['model']} n'est pas installe"))
        elif locked.get("model") != now["model"]:
            drifts.append(
                Drift(
                    role,
                    "modele_change",
                    f"fige : {locked.get('model')}, configure : {now['model']}",
                )
            )
        elif locked.get("digest") != now["digest"]:
            drifts.append(
                Drift(
                    role,
                    "version_changee",
                    f"{now['model']} a change depuis le verrou "
                    f"({locked.get('digest', '')[:12]} -> {now['digest'][:12]}) : re-evaluer",
                )
            )
    return drifts


def golden_summary(results: dict) -> dict:
    """Le score a retenir d'un fichier `resultats.json` de `scripts/run_golden.py`."""
    summary = results["summary"]
    return {
        "passed": summary["total"]["passed"],
        "cases": summary["total"]["cases"],
        "by_category": {k: v["passed"] for k, v in summary.items() if k != "total"},  # fmt: skip
        "date": results.get("meta", {}).get("date", ""),
    }


def regressions(baseline: dict | None, candidate: dict) -> list[str]:
    """Ce qui empire entre deux scores du golden dataset (vide : la mise a jour est permise).

    Une categorie qui baisse bloque, meme si le total monte : un modele qui gagne en
    classement mais perd en hors perimetre n'est pas un meilleur modele pour un decideur.
    """
    if baseline is None:
        return []
    problems = []
    if candidate["cases"] != baseline["cases"]:
        problems.append(
            f"golden dataset different ({baseline['cases']} questions au verrou, "
            f"{candidate['cases']} evaluees) : comparer sur le meme jeu"
        )
        return problems
    if candidate["passed"] < baseline["passed"]:
        problems.append(f"total : {candidate['passed']} contre {baseline['passed']} au verrou")
    for category, before in baseline.get("by_category", {}).items():
        after = candidate.get("by_category", {}).get(category, 0)
        if after < before:
            problems.append(f"{category} : {after} contre {before}")
    return problems


def build(settings: Settings, tags: list[dict], server: str, golden: dict | None,
          overrides: dict[str, str] | None = None) -> dict:  # fmt: skip
    return {
        "locked_at": date.today().isoformat(),
        "ollama": server,
        "roles": snapshot(settings, tags, overrides),
        "golden": golden,
    }


def load(path: Path | None = None) -> dict | None:
    path = path or LOCK_PATH
    return json.loads(path.read_text()) if path.exists() else None


def save(lock: dict, path: Path | None = None) -> None:
    (path or LOCK_PATH).write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n")


def models_of(results: dict) -> dict[str, str]:
    """Les modeles par role d'un fichier de resultats (« planner = gemma4:e4b, ... »)."""
    pairs = (p.split(" = ") for p in results.get("meta", {}).get("models", "").split(", ") if p)
    return {role.strip(): model.strip() for role, model in pairs}
