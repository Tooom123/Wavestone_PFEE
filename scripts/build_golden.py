"""Calcule les reponses attendues du golden dataset et les fige dans docs/eval/golden.json.

    uv run python scripts/build_golden.py          # regenere golden.json
    uv run python scripts/build_golden.py --check  # echoue si golden.json n'est plus a jour

Les faits sont calcules par pandas sur les CSV de `data/` (non versionnes). Relire le diff
de golden.json avant de le commiter : c'est la verite terrain de l'evaluation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent_data.config import DATA_DIR  # noqa: E402
from agent_data.eval import golden  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "docs/eval/golden.json"


def csv_for(dataset: str) -> Path | None:
    folder = DATA_DIR / dataset
    return next(iter(sorted(folder.glob("*.csv"))), None) if folder.exists() else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare sans ecrire")
    parser.add_argument("--out", default=str(GOLDEN))
    args = parser.parse_args(argv)

    cases = golden.build(DATA_DIR, csv_for)
    out = Path(args.out)
    if args.check:
        current = golden.load(out) if out.exists() else []
        if current != cases:
            print(f"{out} n'est plus a jour : relancer build_golden.py", file=sys.stderr)
            return 1
        print(f"{out} est a jour ({len(cases)} questions)")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    golden.dump(cases, out)
    for case in cases:
        print(f"[{case.category:>14}] {case.id:<20} {case.reference_answer}")
    print(f"\n{len(cases)} questions ecrites dans {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
