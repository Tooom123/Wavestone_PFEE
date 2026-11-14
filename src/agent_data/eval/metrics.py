"""Metriques d'evaluation inspirees de RAGAS, calculees sans LLM.

RAGAS juge une reponse avec un LLM. Ici, la verite terrain est chiffree (golden dataset) :
on peut donc verifier les memes proprietes de facon deterministe, reproductible et gratuite.

- `answer_correctness` (RAGAS : answer correctness) : la reponse finale contient-elle les
  faits attendus ?
- `context_recall` (RAGAS : context recall) : les resultats calcules a l'etage 1
  contiennent-ils ces faits ?
- `faithfulness` (RAGAS : faithfulness) : les chiffres de la reponse viennent-ils des
  resultats, ou sont-ils inventes ?
- `abstained` (sans equivalent) : hors perimetre, la reponse dit-elle qu'elle ne sait pas ?

Comparer `context_recall` et `answer_correctness` situe une erreur : faits absents des
resultats = l'etage 1 a mal calcule ; presents dans les resultats mais pas dans la reponse =
l'etage 2 les a perdus.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from agent_data.eval.golden import Fact, GoldenCase
from agent_data.schemas import Artifact

# --------------------------------------------------------------------------- texte

_NUMBER = re.compile(
    r"(?<![\w.,])([-−–]?)(\d{1,3}(?:[   ]\d{3})+|\d+)([.,]\d+)?"
    r"(?:\s*(milliards?|mds?|millions?|m€|m\b|k€|k\b|milliers?))?",
    re.IGNORECASE,
)
_SCALE = {
    "milliard": 1e9,
    "milliards": 1e9,
    "md": 1e9,
    "mds": 1e9,
    "million": 1e6,
    "millions": 1e6,
    "m€": 1e6,
    "m": 1e6,
    "k€": 1e3,
    "k": 1e3,
    "millier": 1e3,
    "milliers": 1e3,
}

ABSTAIN_MARKERS = (
    "ne contient pas",
    "ne contiennent pas",
    "ne permet pas",
    "ne permettent pas",
    "pas de colonne",
    "aucune colonne",
    "aucune donnee",
    "pas de donnee",
    "pas d'information",
    "aucune information",
    "absente",
    "absent des",
    "absentes",
    "pas disponible",
    "indisponible",
    "impossible de",
    "ne figure pas",
    "ne figurent pas",
    "aucun resultat",
    "ne dispose pas",
    "ne disposons pas",
    "ne disposent pas",
    "n'est pas renseigne",
    "hors du perimetre",
)


def words(text: str) -> str:
    """Minuscules, sans accents, mots separes par une espace, bordee d'espaces."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " " + " ".join(re.findall(r"[a-z0-9]+", text.lower())) + " "


def numbers_in(text: str) -> list[float]:
    """Nombres d'un texte, en notation francaise ou anglaise.

    « 1,394 » est ambigu (mille trois cent quatre-vingt-quatorze en anglais, un virgule
    quatre en francais) : les deux lectures sont renvoyees, le controle accepte l'une ou
    l'autre. Les multiplicateurs (« 14,9 millions », « 3,6 M€ ») sont appliques.
    """
    out: list[float] = []
    for match in _NUMBER.finditer(text):
        sign, integer, decimals, scale = match.groups()
        integer = re.sub(r"[   ]", "", integer)
        factor = _SCALE.get((scale or "").lower(), 1.0)
        negative = -1.0 if sign else 1.0
        if decimals:
            readings = {float(f"{integer}.{decimals[1:]}")}
            if decimals[0] == "," and len(decimals) == 4 and not scale:
                readings.add(float(integer + decimals[1:]))  # 1,394 lu a l'anglaise
        else:
            readings = {float(integer)}
        out += [negative * factor * r for r in readings]
    return out


def _close(a: float, b: float, fact: Fact) -> bool:
    if fact.abs_tol is not None:
        return abs(a - b) <= fact.abs_tol
    return math.isclose(a, b, rel_tol=fact.rel_tol, abs_tol=1e-9)


def number_matches(fact: Fact, candidates: Iterable[float]) -> bool:
    if not isinstance(fact.value, int | float):
        return False
    targets = [float(fact.value)]
    if fact.unit == "%":
        targets.append(float(fact.value) / 100)  # 26,5 % ecrit 0,265
    if fact.ignore_sign:
        targets = [abs(t) for t in targets]
        candidates = [abs(c) for c in candidates]
    return any(_close(c, t, fact) for c in candidates for t in targets)


def label_matches(fact: Fact, text: str) -> bool:
    haystack = words(text)
    names = [str(fact.value), *fact.aliases]
    return any(words(n) in haystack for n in names if n.strip())


def abstains(text: str) -> bool:
    haystack = words(text)
    return any(words(marker) in haystack for marker in ABSTAIN_MARKERS)


def fact_in(fact: Fact, text: str, numbers: list[float]) -> bool:
    if fact.kind == "number":
        return number_matches(fact, numbers)
    if fact.kind == "label":
        return label_matches(fact, text)
    return abstains(text)


# ------------------------------------------------------------------------- artefacts


def _walk_numbers(value: Any) -> Iterable[float]:
    if isinstance(value, bool):
        return
    if isinstance(value, int | float):
        if math.isfinite(value):
            yield float(value)
    elif isinstance(value, str):
        yield from numbers_in(value)
    elif isinstance(value, dict):
        for v in value.values():
            yield from _walk_numbers(v)
    elif isinstance(value, list | tuple):
        for v in value:
            yield from _walk_numbers(v)


RAW_ROWS = 100
"""Au-dela, une table ou une serie de figure est un extrait de donnees, pas un resultat."""


def _raw_trace(trace: Any) -> bool:
    return isinstance(trace, dict) and any(
        isinstance(v, list) and len(v) > RAW_ROWS for v in trace.values()
    )


def results_only(artifacts: list[Artifact]) -> list[Artifact]:
    """Retire les extraits de donnees brutes (tables longues, nuages de points).

    Un extrait de 2 240 lignes contient presque n'importe quel nombre : le compter comme
    « resultat » gonflerait le rappel du contexte et la fidelite. C'est aussi ce que
    `run_golden.py` conserve pour pouvoir re-noter une evaluation sans relancer l'agent.
    """
    kept = []
    for art in artifacts:
        payload = art.payload
        if payload.kind == "table" and len(payload.rows) > RAW_ROWS:
            continue
        if payload.kind == "figure":
            data = [t for t in payload.spec.get("data", []) if not _raw_trace(t)]
            art = art.model_copy(
                update={"payload": payload.model_copy(update={"spec": {"data": data}})}
            )
        kept.append(art)
    return kept


def artifacts_content(artifacts: list[Artifact]) -> tuple[str, list[float]]:
    """Le texte et les nombres des resultats de l'etage 1, hors donnees brutes."""
    texts: list[str] = []
    numbers: list[float] = []
    for art in results_only(artifacts):
        texts.append(art.title)
        payload = art.payload
        if payload.kind == "table":
            texts += [str(c) for c in payload.columns]
            texts += [str(v) for row in payload.rows for v in row]
            numbers += list(_walk_numbers(payload.rows))
        elif payload.kind == "finding":
            texts += [payload.statement, payload.evidence]
            numbers += numbers_in(f"{payload.statement} {payload.evidence}")
        else:
            numbers += list(_walk_numbers(payload.spec.get("data", [])))
    return "\n".join(texts), numbers


# ---------------------------------------------------------------------------- scores


@dataclass
class CaseScore:
    case_id: str
    category: str
    answer_correctness: float
    context_recall: float | None
    faithfulness: float | None
    abstained: bool
    passed: bool
    missing: list[str] = field(default_factory=list)
    unsupported: list[float] = field(default_factory=list)


def _claimable(value: float, question: str) -> bool:
    """Nombres a justifier : on ignore les annees, les petits entiers et ceux de la question."""
    if value.is_integer() and (abs(value) <= 12 or 1900 <= value <= 2100):
        return False
    return value not in numbers_in(question)


_MONTHS = (
    "janvier|fevrier|février|mars|avril|mai|juin|juillet|aout|août|septembre|octobre|"
    "novembre|decembre|décembre"
)
_DATES = re.compile(
    rf"\b\d{{4}}-\d{{2}}-\d{{2}}\b|\b\d{{1,2}}/\d{{1,2}}/\d{{2,4}}\b"
    rf"|\b(?:1er|\d{{1,2}})\s+(?:{_MONTHS})(?:\s+\d{{4}})?",
    re.IGNORECASE,
)


def claims_in(answer: str, question: str) -> list[float]:
    """Les chiffres que la reponse avance (hors dates, annees, petits entiers, chiffres de la
    question). « le 30 decembre 2012 » situe une periode, il n'avance pas de resultat."""
    return [n for n in numbers_in(_DATES.sub(" ", answer)) if _claimable(n, question)]


def faithfulness(
    answer: str, numbers: list[float], question: str
) -> tuple[float | None, list[float]]:
    """Part des chiffres de la reponse retrouves dans les resultats (a 1 % pres)."""
    claims = claims_in(answer, question)
    if not claims:
        return None, []
    unsupported = []
    for claim in claims:
        variants = (claim, claim / 100, claim * 100)
        if not any(
            math.isclose(v, n, rel_tol=0.01, abs_tol=0.005) for v in variants for n in numbers
        ):
            unsupported.append(claim)
    return 1 - len(unsupported) / len(claims), unsupported


def score_case(case: GoldenCase, answer: str, artifacts: list[Artifact]) -> CaseScore:
    answer_numbers = numbers_in(answer)
    context_text, context_numbers = artifacts_content(artifacts)
    faith, unsupported = faithfulness(answer, context_numbers, case.question)
    did_abstain = abstains(answer)

    if any(f.kind == "abstain" for f in case.facts):
        # Hors perimetre, la seule bonne reponse est de dire qu'on ne peut pas repondre.
        # Une reponse qui previent puis avance un chiffre de substitution (le profit comme
        # « satisfaction ») echoue : le decideur retiendrait le chiffre.
        honest = did_abstain and not claims_in(answer, case.question)
        return CaseScore(
            case.id,
            case.category,
            answer_correctness=1.0 if honest else 0.0,
            context_recall=None,
            faithfulness=faith,
            abstained=did_abstain,
            passed=honest,
            missing=[] if honest else ["reconnaître que les données ne le permettent pas"],
            unsupported=unsupported,
        )

    # La reponse est jugee sur la formulation attendue qu'elle couvre le mieux.
    # En cas d'egalite, max garde le premier ensemble : la formulation principale.
    scored = []
    for facts in case.fact_sets:
        hits = [fact_in(f, answer, answer_numbers) for f in facts]
        scored.append((sum(hits) / len(facts), facts, hits))
    correctness, facts, found = max(scored, key=lambda item: item[0])
    in_context = [fact_in(f, context_text, context_numbers) for f in facts]
    return CaseScore(
        case.id,
        case.category,
        answer_correctness=correctness,
        context_recall=sum(in_context) / len(facts),
        faithfulness=faith,
        abstained=did_abstain,
        passed=correctness == 1.0,
        missing=[f.name for f, ok in zip(facts, found, strict=True) if not ok],
        unsupported=unsupported,
    )


def mean(values: list[float | None]) -> float | None:
    kept = [v for v in values if v is not None]
    return sum(kept) / len(kept) if kept else None


def summarize(scores: list[CaseScore]) -> dict[str, dict[str, float | int | None]]:
    """Moyennes par categorie, plus une ligne « total »."""
    groups: dict[str, list[CaseScore]] = {}
    for s in scores:
        groups.setdefault(s.category, []).append(s)
    groups["total"] = list(scores)
    return {
        name: {
            "cases": len(items),
            "passed": sum(s.passed for s in items),
            "answer_correctness": mean([s.answer_correctness for s in items]),
            "context_recall": mean([s.context_recall for s in items]),
            "faithfulness": mean([s.faithfulness for s in items]),
        }
        for name, items in groups.items()
    }
