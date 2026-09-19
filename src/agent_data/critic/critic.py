"""Critique : relit le resultat d'execution et decide de la suite.

Sans critique, il ne reste qu'un pipeline : c'est ce noeud qui rend la demarche
*decidee* plutot que *deroulee*. Il tranche entre trois issues — resultat satisfaisant,
correction du code, ou retour au planificateur.

Une erreur d'execution est jugee sans appeler le LLM : c'est deterministe, plus rapide et
plus fiable que de demander son avis a un modele sur une stack trace.
"""

from __future__ import annotations

from agent_data.llm import LLMClient, get_client
from agent_data.llm.parsing import ParseError, extract_json
from agent_data.schemas import AnalysisPlan, Critique, ExecutionResult, ExecutionStatus

SYSTEM_PROMPT = """Tu relis le resultat d'une analyse de donnees et tu juges s'il repond \
vraiment a la question posee.

Tu es exigeant mais pragmatique : un resultat partiel mais correct et exploitable est \
acceptable. Tu reponds UNIQUEMENT par un objet JSON valide."""

_TEMPLATE = """Question analysee :
{question}

Plan suivi :
{steps}

Resultat de l'execution :
  sortie standard : {stdout}
  artefacts produits : {artifacts}

Juge ce resultat au format JSON strict :
{{
  "is_satisfactory": <true|false>,
  "issues": ["<probleme constate>"],
  "suggestion": "<correction concrete a apporter, si besoin>",
  "replan": <true si le plan lui-meme est a revoir, false si seul le code est a corriger>
}}"""


def review(
    plan: AnalysisPlan,
    execution: ExecutionResult,
    *,
    client: LLMClient | None = None,
    known_columns: set[str] | None = None,
) -> Critique:
    """Juge un resultat d'execution.

    `known_columns` liste les noms de colonnes des datasets : ils font partie du schema,
    deja connu du modele, et restent donc lisibles dans les messages d'erreur.
    """
    verdict = _judge_failure(execution, known_columns=known_columns)
    if verdict is not None:
        return verdict

    client = client or get_client()
    prompt = _TEMPLATE.format(
        question=plan.restated_question,
        steps="\n".join(f"  {s.id}. {s.goal}" for s in plan.steps),
        stdout=(execution.stdout or "(vide)")[:3000],
        artifacts=_describe_artifacts(execution),
    )
    try:
        payload = extract_json(client.complete(prompt, system=SYSTEM_PROMPT))
        return Critique.model_validate(payload)
    except (ParseError, ValueError):
        # Un critique illisible ne doit pas bloquer le run : on accepte le resultat,
        # qui a au moins produit des artefacts valides.
        return Critique(
            is_satisfactory=True,
            issues=["Critique illisible : resultat accepte par defaut."],
        )


def _judge_failure(
    execution: ExecutionResult, *, known_columns: set[str] | None = None
) -> Critique | None:
    """Verdict deterministe pour les cas ou le LLM n'apporte rien."""
    if execution.status is ExecutionStatus.TIMEOUT:
        return Critique(
            is_satisfactory=False,
            issues=["Le code a depasse le temps imparti."],
            suggestion=(
                "Simplifier le calcul : echantillonner, eviter les boucles sur les lignes, "
                "preferer les operations vectorisees."
            ),
            replan=False,
        )
    if execution.status is ExecutionStatus.ERROR:
        return Critique(
            is_satisfactory=False,
            issues=[
                "Le code a echoue :\n"
                + _error_essentials(execution.stderr, known_columns=known_columns)
            ],
            suggestion=(
                "Corriger precisement cette erreur. Ne reproduis pas le meme appel : "
                "change la ligne fautive."
            ),
            replan=False,
        )
    if not execution.artifacts:
        return Critique(
            is_satisfactory=False,
            issues=["Aucun artefact n'a ete produit."],
            suggestion=(
                "Ecrire les resultats en JSON dans /workspace/out/ selon le contrat d'artefacts."
            ),
            replan=False,
        )
    return None


#: Au-dela de cette longueur, un fragment sans espace est presque surement une suite de
#: valeurs de donnees recrachees par pandas, pas un message d'erreur.
_MAX_TOKEN_LENGTH = 60


def _looks_like_identifier(value: str) -> bool:
    """Vrai pour un nom de colonne plausible, faux pour une valeur de donnees.

    Un identifiant est court, sans chiffre isole ni ponctuation de donnee. Le doute
    profite au masquage.
    """
    import re as _re

    if len(value) > 40 or any(c in value for c in ",;\t\n"):
        return False
    return bool(_re.fullmatch(r"[A-Za-z][A-Za-z0-9 _.-]*", value)) and not _re.search(
        r"\d{3,}", value
    )


def _error_essentials(
    stderr: str, *, max_chars: int = 2000, known_columns: set[str] | None = None
) -> str:
    """Isole la partie utile d'une trace : la ligne fautive et le message d'erreur.

    Tronquer la fin d'une trace ferait disparaitre le message d'exception, qui est
    justement la seule information dont le modele a besoin pour corriger. Sans lui, il
    regenere le meme code a l'identique.

    La trace est aussi **expurgee des valeurs de donnees** : pandas recopie volontiers
    le contenu fautif dans son message (« could not convert string to float:
    '7590-VHVEG' »). Sans ce filtrage, la boucle de correction reinjecterait des donnees
    brutes dans le contexte du LLM, ce que le projet s'interdit.
    """
    lines = [line for line in stderr.strip().splitlines() if line.strip()]
    if not lines:
        return "(aucune sortie d'erreur)"

    # Les frames internes des bibliotheques n'apprennent rien au modele : ce qui compte
    # est la ligne de SON code et le message final. Une trace pandas profonde repousse
    # sinon le message utile hors de la fenetre conservee.
    own_frames = [
        line
        for index, line in enumerate(lines)
        if "/workspace/code.py" in line or (index and "/workspace/code.py" in lines[index - 1])
    ]

    # La derniere ligne non vide porte le type et le message de l'exception.
    tail = lines[-2:]
    kept = [*own_frames[-4:], *[line for line in tail if line not in own_frames]]
    essentials = "\n".join(kept) if kept else "\n".join(lines[-4:])
    return redact_data_values(essentials, known_columns=known_columns)[-max_chars:]


def redact_data_values(text: str, *, known_columns: set[str] | None = None) -> str:
    """Remplace les fragments qui ressemblent a des valeurs de donnees.

    Heuristique volontairement large : mieux vaut masquer un bout de message technique
    que laisser fuir une valeur du jeu de donnees. Les noms de colonnes sont epargnes,
    car ils appartiennent au schema, que le modele connait deja par le profil.
    """
    import re

    columns = known_columns or set()

    # Valeurs entre quotes simples : c'est ainsi que pandas cite le contenu fautif
    # (« could not convert string to float: '7590-VHVEG' »). Les chemins de fichiers,
    # eux, apparaissent entre quotes doubles dans les traces Python et restent utiles.
    def _mask_quoted(match: re.Match[str]) -> str:
        inner = match.group(1)
        if inner in columns:
            return match.group(0)
        # Un nom de colonne inexistant (KeyError) ressemble a un identifiant : le
        # modele en a besoin pour corriger son code, et ce n'est pas une donnee.
        if _looks_like_identifier(inner):
            return match.group(0)
        return "'<valeur masquee>'"

    text = re.sub(r"'([^']{4,})'", _mask_quoted, text)

    # Longues suites sans espace : concatenations de valeurs (ids, categories...).
    def _mask(match: re.Match[str]) -> str:
        token = match.group(0)
        if "/" in token:  # chemin de fichier : utile au diagnostic
            return token
        return "<valeurs masquees>"

    return re.sub(rf"\S{{{_MAX_TOKEN_LENGTH},}}", _mask, text)


def _describe_artifacts(execution: ExecutionResult) -> str:
    """Decrit les artefacts sans reinjecter tout leur contenu dans le prompt."""
    if not execution.artifacts:
        return "(aucun)"
    lines = []
    for art in execution.artifacts:
        payload = art.payload
        detail = payload.kind
        if payload.kind == "table":
            detail = f"table {len(payload.rows)}x{len(payload.columns)} {payload.columns}"
        elif payload.kind == "finding":
            detail = f"constat : {payload.statement} ({payload.evidence})"
        lines.append(f"  - [{art.step_id}] {art.title} : {detail}")
    return "\n".join(lines)
