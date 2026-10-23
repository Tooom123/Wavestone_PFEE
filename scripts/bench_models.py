"""Compare des modeles Ollama sur les roles de l'agent qui ne demandent pas de sandbox.

    uv run python scripts/bench_models.py gemma4:e4b llama3.2:latest qwen2.5-coder:14b
    uv run python scripts/bench_models.py --roles planner synthesis M1 M2

Chaque role est mesure sur les trois cas d'evaluation, avec les memes entrees pour tous les
modeles :
  - planner   : le plan est-il valide, reformule-t-il la question, cite-t-il des colonnes ?
  - critic    : accepte-t-il de bons resultats et refuse-t-il des resultats hors sujet ?
  - synthesis : la reponse passe-t-elle les controles de l'etage 2 (a artefacts identiques) ?

Le role `coder` exige le sandbox : il se mesure avec `scripts/run_eval.py` en changeant
`CODER_MODEL`.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent_data.config import DATA_DIR, Settings, get_settings  # noqa: E402
from agent_data.critic import review  # noqa: E402
from agent_data.eval import CASES, check_stage1, check_stage2  # noqa: E402
from agent_data.eval.fixtures import OFF_TOPIC, fixture_artifacts  # noqa: E402
from agent_data.llm import OllamaClient  # noqa: E402
from agent_data.llm.parsing import ParseError  # noqa: E402
from agent_data.planner import plan_analysis  # noqa: E402
from agent_data.profiling import profile_csv  # noqa: E402
from agent_data.rendering import synthesize  # noqa: E402
from agent_data.schemas import AnalysisPlan, ExecutionResult, ExecutionStatus  # noqa: E402


@dataclass
class Score:
    passed: int = 0
    total: int = 0
    seconds: float = 0.0
    notes: list[str] = field(default_factory=list)

    def add(self, ok: bool, note: str = "") -> None:
        self.total += 1
        self.passed += ok
        if not ok and note:
            self.notes.append(note)


def _csv(dataset: str) -> Path:
    return next(iter(sorted((DATA_DIR / dataset).glob("*.csv"))))


def bench_planner(client: OllamaClient) -> Score:
    score = Score()
    for case in CASES:
        started = time.monotonic()
        try:
            plan = plan_analysis(case.question, [profile_csv(_csv(case.dataset))], client=client)
        except (ParseError, ValueError) as exc:
            score.add(False, f"{case.id}: plan illisible ({type(exc).__name__})")
            score.seconds += time.monotonic() - started
            continue
        score.seconds += time.monotonic() - started
        for check in check_stage1(case, plan, [_ok_artifact()]):
            score.add(check.passed, f"{case.id}: {check.detail}")
    return score


def _ok_artifact():
    return fixture_artifacts("ventes_qualite")[0]


def bench_critic(client: OllamaClient) -> Score:
    score = Score()
    plan = AnalysisPlan.model_validate(
        {
            "question": "q",
            "restated_question": "Quels facteurs expliquent le depart des clients ?",
            "steps": [{"id": "s1", "goal": "Identifier les facteurs de depart", "method": "ML"}],
        }
    )
    for label, artifacts, expected in (
        ("bon resultat", fixture_artifacts("churn_facteurs"), True),
        ("resultat hors sujet", OFF_TOPIC, False),
    ):
        started = time.monotonic()
        verdict = review(
            plan,
            ExecutionResult(status=ExecutionStatus.SUCCESS, stdout="ok", artifacts=artifacts),
            client=client,
        )
        score.seconds += time.monotonic() - started
        unreadable = any("illisible" in i for i in verdict.issues)
        score.add(
            not unreadable and verdict.is_satisfactory is expected,
            f"{label}: {'JSON illisible' if unreadable else f'verdict {verdict.is_satisfactory}'}",
        )
    return score


def bench_synthesis(client: OllamaClient) -> Score:
    score = Score()
    for case in CASES:
        artifacts = fixture_artifacts(case.id)
        plan = AnalysisPlan.model_validate(
            {
                "question": case.question,
                "restated_question": case.question,
                "steps": [{"id": "s1", "goal": "analyser", "method": "stats"}],
            }
        )
        started = time.monotonic()
        text = synthesize(plan, artifacts, client=client)
        score.seconds += time.monotonic() - started
        for check in check_stage2(case, artifacts, text):
            score.add(check.passed, f"{case.id}: {check.detail}")
        score.notes.append(f"[{case.id}] {text[:400]!r}")
    return score


BENCHES = {"planner": bench_planner, "critic": bench_critic, "synthesis": bench_synthesis}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs="+", help="Modeles Ollama a comparer")
    parser.add_argument("--roles", nargs="+", choices=BENCHES, default=list(BENCHES))
    parser.add_argument("--json", help="Ecrit les resultats dans ce fichier")
    args = parser.parse_args(argv)

    base = get_settings()
    results: dict[str, dict[str, dict]] = {}
    for model in args.models:
        client = OllamaClient(Settings(_env_file=None, llm_base_url=base.llm_base_url), model=model)
        started = time.monotonic()
        client.complete("Reponds : ok")  # charge le modele en VRAM : mesure a part
        load = time.monotonic() - started
        print(f"\n### {model}  (chargement {load:.1f}s)")
        results[model] = {"load_seconds": round(load, 1)}  # type: ignore[dict-item]
        for role in args.roles:
            score = BENCHES[role](client)
            results[model][role] = {
                "passed": score.passed,
                "total": score.total,
                "seconds": round(score.seconds, 1),
                "notes": score.notes,
            }
            print(f"  {role:10} {score.passed}/{score.total} controles  {score.seconds:6.1f}s")
            for note in score.notes:
                if role != "synthesis" or note.startswith("["):
                    print(f"      - {note}")

    if args.json:
        Path(args.json).write_text(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
