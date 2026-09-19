"""Executeur : plan d'analyse -> code Python.

Parti pris « code-as-action » : l'agent ecrit du pandas/scikit-learn reellement execute,
plutot que d'appeler des fonctions predefinies. C'est ce qui garde l'espace d'analyse
ouvert (statistiques comme ML), et c'est ce qui impose le sandbox.

Le code genere doit deposer ses resultats dans `/workspace/out/` au format du contrat
d'artefacts : c'est la frontiere entre l'etage 1 et l'etage 2.
"""

from __future__ import annotations

from agent_data.llm import LLMClient, get_client
from agent_data.llm.parsing import extract_python
from agent_data.sandbox import MountedDataset
from agent_data.schemas import AnalysisPlan, Critique, DatasetProfile

SYSTEM_PROMPT = """Tu ecris du code Python d'analyse de donnees, execute dans un \
conteneur isole, sans acces reseau.

Contraintes absolues :
- Bibliotheques disponibles : pandas, numpy, scipy, scikit-learn, plotly, duckdb, json.
- Aucun acces reseau, aucun `pip install`, aucune lecture hors des chemins indiques.
- Tu lis les CSV avec `pandas.read_csv`, pas avec DuckDB.
- Les noms de colonnes contenant un espace s'ecrivent df['Order Date'] : jamais dans une
  requete SQL, ou ils seraient pris pour des chaines de caracteres.
- Tu convertis explicitement les colonnes de dates avec `pd.to_datetime` avant d'en
  extraire une annee ou un mois.
- Toute valeur ecrite dans un artefact doit etre un type Python natif (int, float, str) :
  convertis les types numpy avec int(), float() ou .item().
- Tu ecris tes resultats dans /workspace/out/ sous forme de fichiers JSON d'artefacts.
- Tu reponds UNIQUEMENT par un bloc de code Python, sans explication autour."""

_ARTIFACT_CONTRACT = """Pour enregistrer tes resultats, utilise le module `agent_out`,
deja installe. N'ecris jamais les fichiers JSON toi-meme :

    from agent_out import save_table, save_figure, save_finding

    save_table(df, "Marge moyenne par categorie", step_id="s1")
    save_figure(fig, "Evolution du CA", step_id="s2")
    save_finding("La categorie Furniture est la moins rentable",
                 evidence="marge moyenne 68 EUR contre 429 pour Technology",
                 confidence=0.9, step_id="s3")

`save_table` accepte un DataFrame pandas, `save_figure` une figure Plotly, et
`save_finding` une phrase de conclusion adossee a un chiffre.

Termine toujours par au moins un `save_finding` qui repond a la question posee."""


def build_prompt(
    plan: AnalysisPlan,
    profiles: list[DatasetProfile],
    datasets: list[MountedDataset],
    *,
    critique: Critique | None = None,
    previous_code: str | None = None,
    previous_error: str | None = None,
) -> str:
    """Construit le prompt de generation de code.

    Quand une critique est fournie, le prompt devient une demande de correction : c'est
    ce qui referme la boucle agentique.
    """
    paths = "\n".join(f"  - '{d.container_path}' (dataset '{d.name}')" for d in datasets)
    steps = "\n".join(
        f"  {s.id}. {s.goal} — methode : {s.method}"
        + (f" — colonnes : {', '.join(s.columns)}" if s.columns else "")
        for s in plan.steps
    )
    schema = "\n".join(
        f"  {p.name} : " + ", ".join(f"{c.name} ({c.kind.value})" for c in p.columns)
        for p in profiles
    )

    sections = [
        f"Question analysee :\n{plan.restated_question}",
        "Hypotheses retenues :\n" + "\n".join(f"  - {a}" for a in plan.assumptions)
        if plan.assumptions
        else "",
        f"Plan a implementer :\n{steps}",
        f"Fichiers CSV disponibles :\n{paths}",
        f"Colonnes :\n{schema}",
        _ARTIFACT_CONTRACT,
    ]

    if previous_code and (critique or previous_error):
        problem = previous_error or ""
        if critique:
            problem = "\n".join(critique.issues) + (
                f"\nCorrection attendue : {critique.suggestion}" if critique.suggestion else ""
            )
        sections.append(
            "Le code precedent doit etre corrige.\n"
            f"Code precedent :\n```python\n{previous_code}\n```\n"
            f"Probleme constate :\n{problem}\n"
            "Produis une version corrigee et complete."
        )
    else:
        sections.append("Produis le script complet qui implemente ce plan.")

    return "\n\n".join(s for s in sections if s)


def generate_code(
    plan: AnalysisPlan,
    profiles: list[DatasetProfile],
    datasets: list[MountedDataset],
    *,
    client: LLMClient | None = None,
    critique: Critique | None = None,
    previous_code: str | None = None,
    previous_error: str | None = None,
) -> str:
    """Demande au LLM le code Python implementant le plan."""
    client = client or get_client()
    prompt = build_prompt(
        plan,
        profiles,
        datasets,
        critique=critique,
        previous_code=previous_code,
        previous_error=previous_error,
    )
    return extract_python(client.complete(prompt, system=SYSTEM_PROMPT))
