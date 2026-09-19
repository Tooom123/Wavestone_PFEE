"""Rendu des artefacts vers les formats de sortie.

Streamlit et le rapport Word/PDF ne sont pas deux developpements concurrents mais deux
*renderers* du meme JSON : le format de sortie peut etre tranche plus tard sans rien
recoder.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from agent_data.schemas import AnalysisPlan, Artifact


@dataclass
class Report:
    """Resultat complet d'un run, independant du format d'affichage."""

    question: str
    restated_question: str
    assumptions: list[str]
    synthesis: str
    artifacts: list[Artifact]
    generated_at: datetime

    @classmethod
    def build(cls, plan: AnalysisPlan, artifacts: list[Artifact], synthesis: str) -> Report:
        return cls(
            question=plan.question,
            restated_question=plan.restated_question,
            assumptions=list(plan.assumptions),
            synthesis=synthesis,
            artifacts=list(artifacts),
            generated_at=datetime.now(),
        )

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "restated_question": self.restated_question,
            "assumptions": self.assumptions,
            "synthesis": self.synthesis,
            "artifacts": [a.model_dump(mode="json") for a in self.artifacts],
            "generated_at": self.generated_at.isoformat(),
        }

    def to_json(self, path: str | Path | None = None, *, indent: int = 2) -> str:
        """Serialise le rapport ; l'ecrit sur disque si `path` est fourni."""
        blob = json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
        if path is not None:
            Path(path).write_text(blob, encoding="utf-8")
        return blob

    def to_markdown(self) -> str:
        """Rendu texte, utile en console et comme base du rendu Word/PDF."""
        lines = [
            f"# {self.question}",
            "",
            self.synthesis,
            "",
            f"**Question analysee :** {self.restated_question}",
        ]
        if self.assumptions:
            lines += ["", "**Hypotheses retenues :**"]
            lines += [f"- {a}" for a in self.assumptions]
        if self.artifacts:
            lines += ["", "## Resultats", ""]
            for art in self.artifacts:
                lines.append(f"### {art.title}")
                payload = art.payload
                if payload.kind == "table":
                    lines.append("| " + " | ".join(payload.columns) + " |")
                    lines.append("|" + "---|" * len(payload.columns))
                    for row in payload.rows[:20]:
                        lines.append("| " + " | ".join(str(v) for v in row) + " |")
                elif payload.kind == "finding":
                    lines.append(f"{payload.statement} — {payload.evidence}")
                else:
                    lines.append("_(figure)_")
                lines.append("")
        return "\n".join(lines)
