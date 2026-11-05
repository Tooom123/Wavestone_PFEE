"""Lance l'evaluation des deux etages sur les cas de reference.

    uv run python scripts/run_eval.py              # les trois cas
    uv run python scripts/run_eval.py --case churn_facteurs
    uv run python scripts/run_eval.py --stage 1    # etage 1 uniquement

Chaque cas fait tourner un vrai run (LLM local + sandbox Docker) : compter quelques
minutes par cas.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent_data.config import DATA_DIR, get_settings  # noqa: E402
from agent_data.eval import CASES, check_stage1, check_stage2  # noqa: E402
from agent_data.gpu import GpuSampler  # noqa: E402
from agent_data.graph import RunTrace, Stage1  # noqa: E402
from agent_data.rendering import synthesize  # noqa: E402
from agent_data.sandbox import SandboxUnavailableError, docker_available  # noqa: E402


def _csv_for(dataset: str) -> Path | None:
    folder = DATA_DIR / dataset
    if not folder.exists():
        return None
    return next(iter(sorted(folder.glob("*.csv"))), None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", help="Identifiant de cas (defaut : tous)")
    parser.add_argument("--stage", type=int, choices=[1, 2], help="N'evalue qu'un etage")
    parser.add_argument("--json", help="Ecrit les mesures (tokens, energie, duree) dans ce fichier")
    args = parser.parse_args(argv)

    if not docker_available():
        print("Docker est indisponible : l'evaluation exige un sandbox.", file=sys.stderr)
        return 1

    selected = CASES
    if args.case:
        by_id = {c.id: c for c in CASES}
        unknown = sorted(set(args.case) - by_id.keys())
        if unknown:
            print(f"Cas inconnu : {', '.join(unknown)}", file=sys.stderr)
            return 1
        selected = [by_id[c] for c in args.case]

    settings = get_settings()
    stage1 = Stage1(settings=settings)
    total = passed = 0
    failures: list[str] = []
    measures: list[dict] = []

    for case in selected:
        csv = _csv_for(case.dataset)
        if csv is None:
            print(f"[skip] {case.id} : dataset '{case.dataset}' absent de data/")
            continue

        print(f"\n=== {case.id}  ({case.family}, {case.dataset})")
        print(f"    {case.question}")
        started = time.monotonic()
        trace = RunTrace()
        before = stage1.usage_by_role()
        sampler = GpuSampler()
        sampler.start()
        try:
            state = stage1.run(case.question, [csv], approve_plan=lambda _: True, trace=trace)
        except SandboxUnavailableError as exc:
            sampler.stop()
            print(f"    ECHEC : {exc}")
            failures.append(case.id)
            continue

        checks = []
        if state.plan is not None and args.stage != 2:
            checks += [("etage1", r) for r in check_stage1(case, state.plan, state.artifacts)]
        if state.plan is not None and args.stage != 1:
            synthesis = synthesize(state.plan, state.artifacts, client=stage1.clients["synthesis"])
            checks += [("etage2", r) for r in check_stage2(case, state.artifacts, synthesis)]

        for stage, result in checks:
            total += 1
            if result.passed:
                passed += 1
            else:
                failures.append(f"{case.id}/{stage}: {result.detail}")
            print(f"    [{'ok ' if result.passed else 'KO '}] {stage} — {result.detail}")

        gpu = sampler.stop()
        after = stage1.usage_by_role()
        # Les compteurs sont cumules sur toute la session : on retient la difference.
        usage = {
            role: {k: round(after[role][k] - before[role][k], 1) for k in after[role]}
            for role in after
        }
        tokens_in = sum(u["prompt_tokens"] for u in usage.values())
        tokens_out = sum(u["completion_tokens"] for u in usage.values())
        duration = time.monotonic() - started
        print(
            f"    {duration:.0f}s, {state.iteration} iteration(s), "
            f"{len(state.artifacts)} artefact(s)"
        )
        print(
            f"    {tokens_in:.0f} tokens en entree, {tokens_out:.0f} en sortie ; "
            f"GPU {gpu.energy_wh:.2f} Wh (moy. {gpu.avg_power_w:.0f} W, "
            f"pic {gpu.peak_power_w:.0f} W, {gpu.peak_memory_mb:.0f} Mo)"
        )
        measures.append(
            {
                "case": case.id,
                "family": case.family,
                "seconds": round(duration, 1),
                "iterations": state.iteration,
                "artifacts": len(state.artifacts),
                "usage": usage,
                "gpu": gpu.as_dict(),
            }
        )

    if args.json:
        Path(args.json).write_text(json.dumps(measures, ensure_ascii=False, indent=2))
        print(f"\nMesures ecrites dans {args.json}")

    print(f"\n{passed}/{total} controle(s) reussi(s)")
    if failures:
        print("Echecs :")
        for failure in failures:
            print(f"  - {failure}")
    return 0 if passed == total and total else 1


if __name__ == "__main__":
    raise SystemExit(main())
