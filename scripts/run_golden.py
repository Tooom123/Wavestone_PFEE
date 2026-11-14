"""Fait tourner l'agent sur le golden dataset et mesure la qualite de ses reponses.

    uv run python scripts/run_golden.py                       # les 24 questions (~25 min)
    uv run python scripts/run_golden.py --category agregat    # une categorie
    uv run python scripts/run_golden.py --case agr_churn      # une question
    uv run python scripts/run_golden.py --juge                # ajoute la note de pertinence

Ecrit docs/eval/resultats.json (brut) et docs/eval/resultats.md (lisible). Il faut Ollama,
le GPU, Docker et les CSV de data/. Voir docs/eval/README.md pour lire les metriques.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent_data.config import DATA_DIR, get_settings  # noqa: E402
from agent_data.eval import golden, metrics, report  # noqa: E402
from agent_data.eval.judge import judge_relevance  # noqa: E402
from agent_data.graph import RunTrace, Stage1  # noqa: E402
from agent_data.llm import get_client  # noqa: E402
from agent_data.planner import plan_analysis  # noqa: E402
from agent_data.profiling import profile_csv  # noqa: E402
from agent_data.rendering import synthesize  # noqa: E402
from agent_data.rendering.synthesis import describe_artifacts  # noqa: E402
from agent_data.sandbox import docker_available  # noqa: E402
from agent_data.schemas import Artifact  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "docs/eval"


def csv_for(dataset: str) -> Path | None:
    folder = DATA_DIR / dataset
    return next(iter(sorted(folder.glob("*.csv"))), None) if folder.exists() else None


def rescore(data: dict, cases: list[golden.GoldenCase]) -> None:
    """Recalcule les notes de chaque reponse enregistree (sans relancer l'agent)."""
    by_id = {c.id: c for c in cases}
    for r in data["results"]:
        kept = [Artifact.model_validate(a) for a in r.get("kept", [])]
        r["score"] = asdict(metrics.score_case(by_id[r["id"]], r["answer"], kept))
        r["reference"] = by_id[r["id"]].reference_answer
    data["summary"] = metrics.summarize([metrics.CaseScore(**r["score"]) for r in data["results"]])


def feasibility(cases: list[golden.GoldenCase], report_path: Path) -> int:
    """Le planificateur refuse-t-il les questions hors perimetre, et seulement elles ?"""
    settings = get_settings()
    client = get_client(settings, "planner")
    rows, errors = [], 0
    for n, case in enumerate(cases, 1):
        csv = csv_for(case.dataset)
        if csv is None:
            continue
        expected = case.category != "hors_perimetre"
        plan = plan_analysis(case.question, [profile_csv(csv, name=case.dataset)], client=client)
        ok = plan.answerable == expected
        errors += not ok
        verdict = "realisable" if plan.answerable else f"refusee : {plan.unanswerable_reason}"
        print(f"[{n}/{len(cases)}] {'ok ' if ok else 'KO '} {case.id} — {verdict}", flush=True)
        rows.append((case, plan.answerable, ok, plan.unanswerable_reason))

    refused = [r for r in rows if r[0].category == "hors_perimetre"]
    accepted = [r for r in rows if r[0].category != "hors_perimetre"]
    lines = [
        "# Contrôle de faisabilité du planificateur\n",
        f"> Généré par `scripts/run_golden.py --faisabilite` le {date.today().isoformat()} — "
        f"planificateur : {settings.model_for('planner')}. Ne pas modifier à la main.\n",
        f"- Questions hors périmètre refusées : **{sum(not r[1] for r in refused)}"
        f"/{len(refused)}**",
        f"- Questions réalisables refusées à tort : **{sum(not r[1] for r in accepted)}"
        f"/{len(accepted)}**\n",
        "| Question | Attendu | Décision | Raison donnée |",
        "|---|---|---|---|",
    ]
    for case, answerable, ok, reason in rows:
        expected = "réalisable" if case.category != "hors_perimetre" else "refus"
        decision = ("✅ " if ok else "❌ ") + ("réalisable" if answerable else "refus")
        lines.append(f"| `{case.id}` | {expected} | {decision} | {reason or '—'} |")
    report_path.write_text("\n".join(lines) + "\n")
    print(f"\n{len(rows) - errors}/{len(rows)} decisions justes ; rapport : {report_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", help="Identifiant de question (repetable)")
    parser.add_argument("--category", action="append", choices=list(golden.CATEGORIES))
    parser.add_argument("--juge", action="store_true", help="Note la pertinence avec un LLM local")
    parser.add_argument("--golden", default=str(EVAL_DIR / "golden.json"))
    parser.add_argument("--out", default=str(EVAL_DIR / "resultats"), help="Sans extension")
    parser.add_argument(
        "--rapport", action="store_true", help="Regenere le rapport depuis le JSON, sans run"
    )
    parser.add_argument(
        "--rescore",
        action="store_true",
        help="Re-note les reponses enregistrees avec golden.json et les metriques actuels",
    )
    parser.add_argument(
        "--faisabilite",
        action="store_true",
        help="N'evalue que le controle de faisabilite du planificateur (sans Docker)",
    )
    args = parser.parse_args(argv)
    out = Path(args.out)

    if args.rapport or args.rescore:
        data = json.loads(out.with_suffix(".json").read_text())
        if args.rescore:
            rescore(data, golden.load(Path(args.golden)))
            out.with_suffix(".json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            )
        out.with_suffix(".md").write_text(report.render(data["results"], data["meta"]))
        print(f"Rapport : {out.with_suffix('.md')}")
        return 0

    if args.faisabilite:
        return feasibility(golden.load(Path(args.golden)), out.with_name("faisabilite.md"))

    if not docker_available():
        print("Docker est indisponible : l'evaluation exige un sandbox.", file=sys.stderr)
        return 1

    cases = golden.load(Path(args.golden))
    if args.case:
        cases = [c for c in cases if c.id in set(args.case)]
    if args.category:
        cases = [c for c in cases if c.category in set(args.category)]
    if not cases:
        print("Aucune question ne correspond aux filtres.", file=sys.stderr)
        return 1

    settings = get_settings()
    stage1 = Stage1(settings=settings)
    started_all = time.monotonic()
    results = []

    for n, case in enumerate(cases, 1):
        print(f"\n[{n}/{len(cases)}] {case.id} ({case.category}) — {case.question}", flush=True)
        csv = csv_for(case.dataset)
        if csv is None:
            print(f"    jeu '{case.dataset}' absent de data/ : question ignoree")
            continue
        started = time.monotonic()
        answer, artifacts, error, iterations = "", [], "", 0
        try:
            state = stage1.run(case.question, [csv], approve_plan=lambda _: True, trace=RunTrace())
            artifacts, iterations = state.artifacts, state.iteration
            if state.plan is not None:
                answer = synthesize(state.plan, artifacts, client=stage1.clients["synthesis"])
        except Exception as exc:  # noqa: BLE001 - une question en echec ne doit pas tout arreter
            error = f"{type(exc).__name__}: {exc}"

        score = metrics.score_case(case, answer, artifacts)
        relevance = None
        if args.juge and answer:
            verdict = judge_relevance(stage1.clients["critic"], case.question, answer)
            relevance = verdict.score if verdict else None

        seconds = time.monotonic() - started
        mark = "ok " if score.passed else "KO "
        print(
            f"    [{mark}] exactitude {report.pct(score.answer_correctness)}, "
            f"rappel {report.pct(score.context_recall)}, fidelite {report.pct(score.faithfulness)}"
            f" — {seconds:.0f}s"
            + (f" — manque : {', '.join(score.missing)}" if score.missing else ""),
            flush=True,
        )
        results.append(
            {
                "id": case.id,
                "category": case.category,
                "question": case.question,
                "reference": case.reference_answer,
                "answer": answer,
                "error": error,
                "score": asdict(score),
                "relevance": relevance,
                "seconds": round(seconds, 1),
                "iterations": iterations,
                "artifacts": len(artifacts),
                # Ce que la synthese a vu : sert de contexte a scripts/ragas_golden.py.
                "context": describe_artifacts(artifacts, max_rows=50),
                # Les resultats hors donnees brutes : de quoi re-noter sans relancer l'agent.
                "kept": [a.model_dump(mode="json") for a in metrics.results_only(artifacts)],
            }
        )

    summary = metrics.summarize([metrics.CaseScore(**r["score"]) for r in results])
    meta = {
        "date": date.today().isoformat(),
        "models": ", ".join(f"{r} = {settings.model_for(r)}" for r in stage1.clients),
        "minutes": (time.monotonic() - started_all) / 60,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"meta": meta, "summary": summary, "results": results}
    out.with_suffix(".json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    out.with_suffix(".md").write_text(report.render(results, meta))
    total = summary["total"]
    print(f"\n{total['passed']}/{total['cases']} questions reussies")
    print(f"Rapport : {out.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
