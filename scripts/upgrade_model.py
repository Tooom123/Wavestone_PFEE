"""Change le modele d'un agent seulement si le golden dataset ne regresse pas.

    uv run python scripts/upgrade_model.py --role coder --model qwen3-coder:14b --pull

1. installe le modele candidat (`--pull`) ;
2. fait tourner le golden dataset avec ce modele pour ce role (~25 min, Docker requis) ;
3. compare au score du verrou (`models.lock.json`) : total et chaque categorie ;
4. sans regression, met a jour le verrou et indique la ligne de `.env` a changer ;
   sinon, le verrou reste tel quel et les regressions sont listees.

Le meme script sert a re-valider un modele dont la version a change sous le meme nom
(`agent-data modeles verifier` signale « version_changee ») : `--model` = le nom actuel.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess  # nosec B404 - commandes fixes, sans shell
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent_data import model_lock  # noqa: E402
from agent_data.config import ROLES, get_settings  # noqa: E402
from agent_data.llm import OllamaClient  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True, choices=list(ROLES))
    parser.add_argument("--model", required=True, help="Nom Ollama du modele candidat")
    parser.add_argument("--pull", action="store_true", help="Telecharge le modele s'il manque")
    parser.add_argument("--out", default=str(ROOT / ".agent_data" / "candidat"))
    args = parser.parse_args(argv)

    lock = model_lock.load()
    if lock is None or not lock.get("golden"):
        print("Pas de score de reference : « agent-data modeles figer --golden ... » d'abord.")
        return 1

    settings = get_settings()
    ollama = OllamaClient(settings)
    if args.model not in ollama.installed_models():
        if not args.pull:
            print(f"{args.model} n'est pas installe (ajouter --pull).", file=sys.stderr)
            return 1
        subprocess.run(["ollama", "pull", args.model], check=True)  # nosec B603 B607

    print(f"Golden dataset avec {args.role} = {args.model} ...", flush=True)
    env = os.environ | {f"{args.role.upper()}_MODEL": args.model}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(  # nosec B603 - interpreteur et script du depot
        [sys.executable, str(ROOT / "scripts/run_golden.py"), "--out", str(out)],
        check=True,
        env=env,
        cwd=ROOT,
    )
    candidate = model_lock.golden_summary(json.loads(out.with_suffix(".json").read_text()))
    baseline = lock["golden"]
    print(f"\nCandidat : {candidate['passed']}/{candidate['cases']} — verrou : "
          f"{baseline['passed']}/{baseline['cases']}")  # fmt: skip

    problems = model_lock.regressions(baseline, candidate)
    if problems:
        print("Regression : le modele n'est pas adopte, le verrou reste inchange.")
        for p in problems:
            print(f"  - {p}")
        return 1

    tags = ollama.tags()
    updated = model_lock.build(
        settings, tags, ollama.server_version(), candidate, overrides={args.role: args.model}
    )
    model_lock.save(updated)
    print(f"Adopte. Verrou mis a jour ; dans .env : {args.role.upper()}_MODEL={args.model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
