# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "ragas==0.4.3",
#     "langchain-community>=0.3.31,<0.4",
#     "langchain-openai>=1.7.4",
# ]
# ///
"""Note les reponses du golden dataset avec RAGAS, juge local via Ollama.

    uv run python scripts/run_golden.py     # d'abord : produit docs/eval/resultats.json
    uv run scripts/ragas_golden.py          # puis : ajoute les notes RAGAS

Script autonome : uv installe RAGAS dans un environnement a part (en-tete ci-dessus), sans
toucher aux dependances de l'agent. RAGAS fige des versions de LangChain incompatibles avec
celles du projet ; voir docs/eval/README.md pour le detail.

Notes calculees (lecture detaillee : docs/eval/README.md) :
  - answer_accuracy : la reponse concorde-t-elle avec la reponse de reference ? Bon second
    avis : sur 24 vraies reponses, une note <= 0,25 signale 5 echecs sur 7 sans fausse alerte.
  - faithfulness : chaque affirmation est-elle appuyee par les resultats ? Bruitee sur nos
    reponses (penalise les phrases de methode) : a lire avec prudence.
La reussite d'une question reste decidee par les metriques deterministes du projet.
Rien ne sort du poste : le juge est un modele Ollama local.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "docs/eval/resultats.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default=str(RESULTS))
    parser.add_argument("--model", default="qwen2.5-coder:14b", help="Juge Ollama")
    parser.add_argument(
        "--base-url", default=os.environ.get("LLM_BASE_URL", "http://localhost:11434")
    )
    args = parser.parse_args()

    from openai import AsyncOpenAI
    from ragas.llms import llm_factory
    from ragas.metrics.collections import AnswerAccuracy, Faithfulness

    # RAGAS appelle le modele en asynchrone : un client synchrone fait echouer chaque note.
    client = AsyncOpenAI(base_url=f"{args.base_url.rstrip('/')}/v1", api_key="ollama")
    llm = llm_factory(args.model, client=client)
    faithfulness, accuracy = Faithfulness(llm=llm), AnswerAccuracy(llm=llm)

    path = Path(args.results)
    data = json.loads(path.read_text())
    for n, r in enumerate(data["results"], 1):
        started = time.monotonic()
        notes: dict[str, float | None] = {"faithfulness": None, "answer_accuracy": None}
        if r["answer"]:
            for key, compute in (
                ("faithfulness", lambda r=r: faithfulness.score(
                    user_input=r["question"], response=r["answer"],
                    retrieved_contexts=[r.get("context") or "(aucun resultat)"])),
                ("answer_accuracy", lambda r=r: accuracy.score(
                    user_input=r["question"], response=r["answer"], reference=r["reference"])),
            ):  # fmt: skip
                try:
                    value = float(compute().value)
                except Exception as exc:  # noqa: BLE001 - une note manquante ne bloque pas
                    print(f"    {key} : {type(exc).__name__}")
                    continue
                # AnswerAccuracy renvoie NaN au lieu d'une erreur quand l'appel echoue.
                notes[key] = None if math.isnan(value) else round(value, 2)
        r["ragas"] = notes
        print(
            f"[{n}/{len(data['results'])}] {r['id']} {notes} ({time.monotonic() - started:.0f} s)"
        )

    data["meta"]["ragas_judge"] = args.model
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"Notes RAGAS ajoutees a {path} ; regenerer le rapport : scripts/run_golden.py --rapport")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
