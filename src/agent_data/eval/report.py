"""Rapport Markdown d'une evaluation sur le golden dataset."""

from __future__ import annotations

from typing import Any

from agent_data.eval.golden import CATEGORIES

METRICS = (
    ("answer_correctness", "Exactitude"),
    ("context_recall", "Rappel du contexte"),
    ("faithfulness", "Fidélité"),
    ("relevance", "Pertinence (juge)"),
)


def pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.0f} %"


def _table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    return "\n".join(lines + ["| " + " | ".join(r) + " |" for r in rows])


def render(results: list[dict[str, Any]], summary: dict[str, dict[str, Any]], meta: dict) -> str:
    with_judge = any(r.get("relevance") is not None for r in results)
    metrics = [m for m in METRICS if with_judge or m[0] != "relevance"]
    parts = [
        "# Évaluation sur le golden dataset\n",
        f"> Généré par `scripts/run_golden.py` le {meta['date']} — modèles : {meta['models']}. "
        "Ne pas modifier à la main.\n",
        f"**{summary['total']['passed']} questions réussies sur {summary['total']['cases']}** "
        f"en {meta['minutes']:.0f} min. Une question est réussie quand la réponse finale contient "
        "tous les faits attendus (ou, hors périmètre, reconnaît qu'elle ne peut pas répondre).\n",
        "## Par catégorie\n",
    ]
    rows = []
    for key in [*CATEGORIES, "total"]:
        if key not in summary:
            continue
        s = summary[key]
        label = "**Total**" if key == "total" else CATEGORIES[key]
        rows.append([label, f"{s['passed']}/{s['cases']}", *[pct(s.get(m)) for m, _ in metrics]])
    parts.append(_table(["Catégorie", "Réussies", *[t for _, t in metrics]], rows))

    parts.append("\n## Par question\n")
    rows = []
    for r in results:
        sc = r["score"]
        rows.append(
            [
                f"`{r['id']}`",
                "✅" if sc["passed"] else "❌",
                *[pct(r.get(m) if m == "relevance" else sc.get(m)) for m, _ in metrics],
                f"{r['seconds']:.0f} s",
                ", ".join(sc["missing"]) or "—",
            ]
        )
    parts.append(
        _table(["Question", "", *[t for _, t in metrics], "Durée", "Faits manquants"], rows)
    )

    parts.append("\n## Réponses\n")
    for r in results:
        sc = r["score"]
        parts.append(f"### `{r['id']}` — {r['question']}\n")
        parts.append(f"- **Attendu** : {r['reference']}")
        if sc["unsupported"]:
            shown = ", ".join(f"{v:g}" for v in sc["unsupported"][:6])
            parts.append(f"- **Chiffres non retrouvés dans les résultats** : {shown}")
        if r.get("error"):
            parts.append(f"- **Erreur** : {r['error']}")
        answer = (r["answer"] or "(aucune réponse)").strip().replace("\n", "\n> ")
        parts.append(f"\n> {answer}\n")
    return "\n".join(parts) + "\n"
