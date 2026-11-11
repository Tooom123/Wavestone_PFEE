"""Rapport Markdown d'une evaluation sur le golden dataset."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent_data.eval.golden import CATEGORIES

Getter = Callable[[dict[str, Any]], float | None]


def _score(key: str) -> Getter:
    return lambda r: r["score"].get(key)


def _ragas(key: str) -> Getter:
    return lambda r: (r.get("ragas") or {}).get(key)


METRICS: tuple[tuple[str, str, Getter], ...] = (
    ("answer_correctness", "Exactitude", _score("answer_correctness")),
    ("context_recall", "Rappel du contexte", _score("context_recall")),
    ("faithfulness", "Fidélité (chiffres)", _score("faithfulness")),
    ("relevance", "Pertinence (juge)", lambda r: r.get("relevance")),
    ("ragas_faithfulness", "RAGAS fidélité", _ragas("faithfulness")),
    ("ragas_answer_accuracy", "RAGAS concordance", _ragas("answer_accuracy")),
)


def pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.0f} %"


def _mean(values: list[float | None]) -> float | None:
    kept = [v for v in values if v is not None]
    return sum(kept) / len(kept) if kept else None


def _table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    return "\n".join(lines + ["| " + " | ".join(r) + " |" for r in rows])


def render(results: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    # Une colonne n'apparait que si au moins une question a une note (juge, RAGAS optionnels).
    shown = [(k, t, g) for k, t, g in METRICS if any(g(r) is not None for r in results)]
    passed = sum(r["score"]["passed"] for r in results)
    judge = f" ; juge RAGAS : {meta['ragas_judge']}" if meta.get("ragas_judge") else ""
    parts = [
        "# Évaluation sur le golden dataset\n",
        f"> Généré par `scripts/run_golden.py` le {meta['date']} — modèles : {meta['models']}"
        f"{judge}. Ne pas modifier à la main.\n",
        f"**{passed} questions réussies sur {len(results)}** en {meta['minutes']:.0f} min. Une "
        "question est réussie quand la réponse finale contient tous les faits attendus (ou, hors "
        "périmètre, reconnaît qu'elle ne peut pas répondre sans avancer de chiffre).\n",
        "## Par catégorie\n",
    ]
    rows = []
    for key in [*CATEGORIES, "total"]:
        group = [r for r in results if key in ("total", r["category"])]
        if not group:
            continue
        label = "**Total**" if key == "total" else CATEGORIES[key]
        done = sum(r["score"]["passed"] for r in group)
        rows.append(
            [label, f"{done}/{len(group)}", *[pct(_mean([g(r) for r in group])) for *_, g in shown]]
        )
    parts.append(_table(["Catégorie", "Réussies", *[t for _, t, _ in shown]], rows))

    parts.append("\n## Par question\n")
    rows = [
        [
            f"`{r['id']}`",
            "✅" if r["score"]["passed"] else "❌",
            *[pct(g(r)) for *_, g in shown],
            f"{r['seconds']:.0f} s",
            ", ".join(r["score"]["missing"]) or "—",
        ]
        for r in results
    ]
    parts.append(
        _table(["Question", "", *[t for _, t, _ in shown], "Durée", "Faits manquants"], rows)
    )

    parts.append("\n## Réponses\n")
    for r in results:
        sc = r["score"]
        parts.append(f"### `{r['id']}` — {r['question']}\n")
        parts.append(f"- **Attendu** : {r['reference']}")
        if sc["unsupported"]:
            values = ", ".join(f"{v:g}" for v in sc["unsupported"][:6])
            parts.append(f"- **Chiffres non retrouvés dans les résultats** : {values}")
        if r.get("error"):
            parts.append(f"- **Erreur** : {r['error']}")
        answer = (r["answer"] or "(aucune réponse)").strip().replace("\n", "\n> ")
        parts.append(f"\n> {answer}\n")
    return "\n".join(parts) + "\n"
