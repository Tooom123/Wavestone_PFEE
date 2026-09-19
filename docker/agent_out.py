"""Helpers d'ecriture des artefacts, disponibles dans le sandbox.

Un modele de 14B ne respecte pas de maniere fiable un contrat JSON decrit en prose : il
oublie le champ `kind`, le traduit, ou invente la forme du payload. Plutot que de durcir
le prompt indefiniment, on lui donne trois fonctions a appeler. La forme correcte devient
alors la plus simple a produire.
"""

from __future__ import annotations

import json
import os
from typing import Any

OUT_DIR = os.environ.get("AGENT_OUT_DIR", "/workspace/out")

_counter = 0


def _write(payload: dict[str, Any], title: str, step_id: str) -> None:
    global _counter
    _counter += 1
    os.makedirs(OUT_DIR, exist_ok=True)
    artifact = {
        "id": f"a{_counter}",
        "step_id": step_id,
        "title": title,
        "payload": payload,
    }
    path = os.path.join(OUT_DIR, f"artifact_{_counter:02d}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(artifact, handle, ensure_ascii=False)


def save_table(df: Any, title: str, step_id: str = "s1", max_rows: int = 200) -> None:
    """Enregistre un DataFrame (ou un dict de colonnes) comme tableau de resultats."""
    frame = df.reset_index() if hasattr(df, "reset_index") and df.index.name else df
    if hasattr(frame, "columns"):
        head = frame.head(max_rows)
        columns = [str(c) for c in head.columns]
        rows = [[_native(v) for v in row] for row in head.itertuples(index=False)]
    else:  # dict de listes
        columns = [str(c) for c in frame]
        rows = [[_native(frame[c][i]) for c in columns] for i in range(len(frame[columns[0]]))]
    _write({"kind": "table", "columns": columns, "rows": rows}, title, step_id)


def save_figure(fig: Any, title: str, step_id: str = "s1") -> None:
    """Enregistre une figure Plotly."""
    spec = json.loads(fig.to_json()) if hasattr(fig, "to_json") else dict(fig)
    _write({"kind": "figure", "spec": spec}, title, step_id)


def save_finding(
    statement: str, evidence: str = "", confidence: float = 0.8, step_id: str = "s1"
) -> None:
    """Enregistre un constat en langage naturel, adosse a un chiffre."""
    _write(
        {
            "kind": "finding",
            "statement": str(statement),
            "evidence": str(evidence),
            "confidence": float(confidence),
        },
        statement[:80],
        step_id,
    )


def _native(value: Any) -> Any:
    """Convertit les scalaires numpy/pandas en types JSON natifs."""
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)
