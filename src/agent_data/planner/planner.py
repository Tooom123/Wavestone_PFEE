"""Planificateur : question metier + profil -> plan d'analyse structure.

C'est la piece qui porte la valeur du systeme. La difficulte n'est pas le ML mais la
**traduction d'une question metier en question statistique bien posee** : « la qualite des
ventes est-elle bonne ? » n'a pas de definition. Le plan doit donc expliciter la
reformulation retenue et les hypotheses prises, pour qu'elles soient discutables.
"""

from __future__ import annotations

from agent_data.llm import LLMClient, get_client
from agent_data.llm.parsing import extract_json
from agent_data.schemas import AnalysisPlan, DatasetProfile

SYSTEM_PROMPT = """Tu es analyste de donnees senior. Tu traduis une question metier, \
souvent vague, en une demarche d'analyse statistique precise et realisable.

Regles :
- Tu ne vois JAMAIS les donnees brutes, seulement leur profil (schema, types, statistiques).
- Tu n'utilises que des colonnes presentes dans le profil fourni.
- Quand la question est ambigue, tu choisis une definition mesurable et tu l'ecris \
explicitement dans les hypotheses.
- Tu reponds UNIQUEMENT par un objet JSON valide, sans commentaire autour."""

_TEMPLATE = """Question metier posee par un decideur :
{question}

Profil des donnees disponibles :
{profiles}

Produis un plan d'analyse au format JSON strict :
{{
  "question": "<la question metier, telle quelle>",
  "restated_question": "<la meme question reformulee en question statistique precise>",
  "assumptions": ["<definition retenue pour chaque terme ambigu>"],
  "datasets": [{dataset_names}],
  "steps": [
    {{
      "id": "s1",
      "goal": "<ce que l'etape etablit, en une phrase>",
      "method": "<methode statistique ou ML>",
      "columns": ["<colonnes du profil>"],
      "rationale": "<en quoi cela repond a la question metier>"
    }}
  ]
}}

Entre 2 et {max_steps} etapes. Chaque colonne citee doit exister dans le profil."""


def render_profile(profile: DatasetProfile) -> str:
    """Rend un profil sous forme compacte pour le prompt.

    Format textuel plutot que JSON brut : a contenu egal il consomme nettement moins de
    tokens, ce qui compte avec un modele local a fenetre limitee.
    """
    lines = [
        f"Dataset '{profile.name}' — {profile.row_count} lignes, {len(profile.columns)} colonnes"
    ]
    for col in profile.columns:
        parts = [f"  - {col.name} ({col.kind.value}, {col.dtype})"]
        if col.null_ratio:
            parts.append(f"nulls={col.null_ratio:.1%}")
        parts.append(f"distinctes={col.unique_count}")
        if col.stats and col.stats.min is not None:
            parts.append(
                f"min={col.stats.min:.4g} med={col.stats.median:.4g} max={col.stats.max:.4g}"
            )
        if col.top_values:
            parts.append(f"valeurs={col.top_values[:5]}")
        lines.append(", ".join(parts))
    return "\n".join(lines)


def build_prompt(question: str, profiles: list[DatasetProfile], *, max_steps: int = 5) -> str:
    """Construit le prompt du planificateur."""
    names = ", ".join(f'"{p.name}"' for p in profiles)
    return _TEMPLATE.format(
        question=question,
        profiles="\n\n".join(render_profile(p) for p in profiles),
        dataset_names=names,
        max_steps=max_steps,
    )


def plan_analysis(
    question: str,
    profiles: list[DatasetProfile],
    *,
    client: LLMClient | None = None,
    max_steps: int = 5,
) -> AnalysisPlan:
    """Demande un plan d'analyse au LLM et le valide.

    Les colonnes inventees par le modele (hallucinations) sont retirees : le code genere
    ensuite planterait dessus, autant les filtrer au plus tot.
    """
    if not profiles:
        raise ValueError("Au moins un profil de dataset est requis pour planifier.")

    client = client or get_client()
    prompt = build_prompt(question, profiles, max_steps=max_steps)
    raw = client.complete(prompt, system=SYSTEM_PROMPT)
    payload = extract_json(raw)

    payload.setdefault("question", question)
    payload.setdefault("restated_question", question)
    payload.setdefault("datasets", [p.name for p in profiles])
    plan = AnalysisPlan.model_validate(payload)
    return _drop_unknown_columns(plan, profiles)


def _drop_unknown_columns(plan: AnalysisPlan, profiles: list[DatasetProfile]) -> AnalysisPlan:
    """Retire des etapes les colonnes absentes des profils."""
    known = {col.name for profile in profiles for col in profile.columns}
    for step in plan.steps:
        step.columns = [c for c in step.columns if c in known]
    return plan
