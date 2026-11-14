"""Etage 2 : artefacts JSON -> synthese en langage naturel.

Cet etage ne voit que les artefacts produits par l'etage 1, jamais les donnees ni le code.
C'est ce qui le rend evaluable separement : a artefacts identiques, la synthese doit etre
reproductible.
"""

from __future__ import annotations

from agent_data.llm import LLMClient, get_client
from agent_data.schemas import AnalysisPlan, Artifact

SYSTEM_PROMPT = """Tu restitues des resultats d'analyse a un decideur non technique.

Regles :
- Tu reponds a la question posee, directement, des la premiere phrase.
- Tu t'appuies uniquement sur les resultats fournis : aucun chiffre invente.
- Tu rappelles les hypotheses retenues quand elles changent la lecture du resultat.
- Quand tu compares des groupes, tu cites la valeur de chaque groupe (taux, moyenne) avant \
de conclure, et ta conclusion va dans le sens de ces valeurs : si les seniors partent a \
41 % contre 24 %, ils partent davantage, quel que soit le coefficient d'un modele.
- Pas de jargon statistique inutile, pas de code, pas de Markdown."""

_TEMPLATE = """Question posee :
{question}

Reformulation analysee :
{restated}

Hypotheses retenues :
{assumptions}

Resultats obtenus :
{artifacts}

Redige la reponse au decideur en 3 a 6 phrases."""


#: Au-dela de cette proportion de valeurs distinctes, une colonne texte est suspecte.
_IDENTIFIER_RATIO = 0.9

#: En dessous de ce nombre de modalites, une colonne texte est une categorie metier
#: (« Furniture », « Technology »...) : elle doit rester lisible, la synthese en a besoin.
_MAX_CATEGORY_VALUES = 25


def _is_identifier_column(values: list) -> bool:
    """Vrai si une colonne se comporte comme un identifiant plutot qu'une categorie.

    Le critere decisif est le nombre **absolu** de modalites, pas leur proportion : une
    table de 3 categories a 100 % de valeurs distinctes sans etre un identifiant.
    """
    textual = [v for v in values if isinstance(v, str)]
    if len(textual) < len(values) * 0.9 or not textual:
        return False

    distinct = set(textual)
    if len(distinct) <= _MAX_CATEGORY_VALUES:
        return False  # categorie metier : on la garde lisible

    return len(distinct) >= _IDENTIFIER_RATIO * len(textual)


def summarize_for_llm(payload, *, max_rows: int) -> tuple[list[str], list[list], str]:
    """Reduit une table a ce que l'etage 2 a le droit de voir.

    L'artefact stocke conserve ses valeurs — le rapport en a besoin. Mais une colonne
    d'identifiants n'a rien a faire dans le contexte du LLM : elle est remplacee par un
    marqueur, et les colonnes numeriques par leurs bornes. Le modele peut alors decrire
    la tendance sans citer un client nommement.
    """
    columns = list(payload.columns)
    rows = payload.rows
    masked_indices = {
        index
        for index in range(len(columns))
        if _is_identifier_column([row[index] for row in rows if index < len(row)])
    }

    note = ""
    if masked_indices:
        names = ", ".join(columns[i] for i in sorted(masked_indices))
        note = f"\n  (colonne(s) d'identifiants masquee(s) : {names} — ne pas citer de valeur)"

    kept: list[list] = []
    for row in rows[:max_rows]:
        kept.append(
            ["<identifiant masque>" if i in masked_indices else v for i, v in enumerate(row)]
        )
    return columns, kept, note


def describe_artifacts(artifacts: list[Artifact], *, max_rows: int = 12) -> str:
    """Rend les artefacts sous forme lisible pour le prompt de synthese.

    Les identifiants sont masques : voir :func:`summarize_for_llm`.
    """
    if not artifacts:
        return "(aucun resultat)"

    blocks: list[str] = []
    for art in artifacts:
        payload = art.payload
        if payload.kind == "table":
            columns, shown, note = summarize_for_llm(payload, max_rows=max_rows)
            head = " | ".join(columns)
            rows = [" | ".join(str(v) for v in row) for row in shown]
            extra = (
                f"\n  ... ({len(payload.rows) - max_rows} lignes supplementaires)"
                if len(payload.rows) > max_rows
                else ""
            )
            blocks.append(f"[{art.title}]\n  {head}\n  " + "\n  ".join(rows) + extra + note)
        elif payload.kind == "finding":
            confidence = f" (confiance {payload.confidence:.0%})" if payload.confidence else ""
            blocks.append(f"[{art.title}] {payload.statement}{confidence} — {payload.evidence}")
        else:  # figure
            blocks.append(f"[{art.title}] figure disponible")
    return "\n\n".join(blocks)


def synthesize(
    plan: AnalysisPlan,
    artifacts: list[Artifact],
    *,
    client: LLMClient | None = None,
) -> str:
    """Produit la reponse en langage naturel destinee au decideur."""
    if not plan.answerable:
        return abstention(plan)
    if not artifacts:
        return (
            "L'analyse n'a produit aucun resultat exploitable. "
            "La question doit etre reformulee ou les donnees completees."
        )

    client = client or get_client()
    prompt = _TEMPLATE.format(
        question=plan.question,
        restated=plan.restated_question,
        assumptions="\n".join(f"  - {a}" for a in plan.assumptions) or "  (aucune)",
        artifacts=describe_artifacts(artifacts),
    )
    return client.complete(prompt, system=SYSTEM_PROMPT)


def abstention(plan: AnalysisPlan) -> str:
    """Reponse fixe quand les donnees ne couvrent pas la question : ni LLM, ni chiffre.

    Le texte est ecrit ici plutot que par le modele : une reponse hors perimetre doit dire
    clairement qu'elle ne sait pas, sans proposer d'indicateur de substitution.
    """
    reason = plan.unanswerable_reason.strip().rstrip(".") or "l'information demandée n'y figure pas"
    return (
        f"Les données disponibles ne permettent pas de répondre à cette question : {reason}. "
        "Aucun calcul n'a été lancé. Pour y répondre, il faudrait des données qui contiennent "
        "cette information."
    )
