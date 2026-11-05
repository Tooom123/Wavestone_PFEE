"""Genere le benchmark de couts (docs/finops/benchmark.md) a partir de mesures reelles.

    uv run python scripts/run_eval.py --json docs/finops/mesures.json   # une fois, GPU + Docker
    uv run python scripts/finops_report.py                               # regenere le rapport

Changer une hypothese : la modifier dans `Hypotheses` (src/agent_data/finops.py) ou passer
`--set cle=valeur` (ex. `--set electricity_eur_per_kwh=0.25`), puis regenerer.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent_data import finops  # noqa: E402
from agent_data.finops import Hypotheses, Profile, Scenario  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
VOLUMES = (100, 1_000, 10_000)
SENSITIVITY = (
    ("electricity_eur_per_kwh", "Prix de l'électricité"),
    ("workstation_capex_eur", "Prix du poste"),
    ("ops_eur_per_hour", "Coût horaire d'exploitation"),
    ("ops_hours_onprem", "Heures d'exploitation du poste local par mois"),
    ("usd_to_eur", "Taux USD → EUR"),
)
FACTORS = (0.5, 1.0, 2.0)


def fr(text: str) -> str:
    """Notation française : virgule décimale, espace pour les milliers."""
    return text.replace(",", " ").replace(".", ",")


def eur(value: float) -> str:
    decimals = 4 if value < 0.01 else 3 if value < 1 else 2
    return fr(f"{value:,.{decimals}f} €")


def table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(out)


def cell(scenario: Scenario, runs: int) -> str:
    text = eur(scenario.unit(runs))
    return text if scenario.feasible(runs) else f"{text} ⚠ saturé"


def render(profile: Profile, h: Hypotheses, measures_name: str) -> str:
    all_scenarios = finops.scenarios(profile, h)
    by_key = {s.key: s for s in all_scenarios}
    parts: list[str] = []

    parts.append(
        f"# Benchmark coûts : on-premise contre cloud\n\n"
        f"> Généré le {date.today().isoformat()} par `scripts/finops_report.py` à partir de "
        f"`{measures_name}`. Ne pas modifier à la main : changer une hypothèse et regénérer.\n"
    )

    parts.append("## 1. Ce que coûte un run (mesuré)\n")
    parts.append(
        table(
            ["Grandeur", "Valeur"],
            [
                ["Durée moyenne", fr(f"{profile.seconds:.0f} s")],
                ["Tokens en entrée", fr(f"{profile.prompt_tokens:,.0f}")],
                ["Tokens en sortie", fr(f"{profile.completion_tokens:,.0f}")],
                ["Énergie GPU", fr(f"{profile.gpu_energy_wh:.2f} Wh")],
            ],
        )
    )
    parts.append(
        "\nMesures faites sur la RTX 4070 SUPER avec `qwen2.5-coder:14b` et `gemma4:e4b`, "
        "sur les cas de référence de `agent_data.eval`. L'énergie est celle du GPU seul "
        "(`nvidia-smi`) ; le reste du poste est une hypothèse.\n"
    )

    parts.append("## 2. Coût par run selon le volume mensuel\n")
    rows = [[s.label, *[cell(s, v) for v in VOLUMES]] for s in all_scenarios]
    parts.append(table(["Mode", *[fr(f"{v:,} runs/mois") for v in VOLUMES]], rows))
    parts.append(
        "\n« ⚠ saturé » : le volume dépasse ce que la machine peut absorber "
        f"({h.utilization * 100:.0f} % d'occupation, un run à la fois) ; le coût affiché est alors "
        "théorique. Une API n'a pas de limite de capacité.\n"
    )

    parts.append("### Détail mensuel à 1 000 runs\n")
    rows = []
    for s in all_scenarios:
        detail = ", ".join(f"{k} {eur(v)}" for k, v in s.fixed.items())
        var = ", ".join(f"{k} {eur(v * 1000)}" for k, v in s.variable.items())
        capacity = "illimitée" if s.capacity_runs is None else f"{s.capacity_runs:,.0f}"
        rows.append([s.label, eur(s.monthly(1000)), detail, var or "—", fr(capacity)])
    parts.append(table(["Mode", "Total / mois", "Fixe", "Variable", "Capacité (runs/mois)"], rows))

    parts.append("\n## 3. Points morts\n")
    local = by_key["onprem"]
    rows = []
    for s in all_scenarios:
        if s.key == "onprem":
            continue
        runs = finops.break_even_runs(local, s)
        if runs is None:
            winner = local if local.monthly(1000) <= s.monthly(1000) else s
            verdict = f"{winner.label} est moins cher à tout volume"
        elif local.variable_total < s.variable_total:
            verdict = f"le poste local devient moins cher au-delà de {runs:,.0f} runs/mois"
        else:
            verdict = f"le poste local est moins cher jusqu'à {runs:,.0f} runs/mois"
        if runs is not None and local.capacity_runs and runs > local.capacity_runs:
            verdict += " (au-delà de la capacité du poste : sans effet pratique)"
        rows.append([s.label, fr(verdict)])
    parts.append(table(["Comparé au poste local", "Résultat"], rows))

    parts.append("\n## 4. Sensibilité (coût par run à 1 000 runs/mois)\n")
    for name, title in SENSITIVITY:
        rows = finops.sensitivity(profile, h, name, FACTORS, 1000)
        parts.append(f"**{title}** (valeur de base : {fr(str(asdict(h)[name]))})\n")
        keys = ["onprem", "l40s-24-7", "api-haiku", "api-sonnet", "api-opus"]
        parts.append(
            table(
                ["Facteur", *[by_key[k].label for k in keys]],
                [[fr(f"×{r['factor']}"), *[eur(r["unit_costs"][k]) for k in keys]] for r in rows],
            )
            + "\n"
        )

    parts.append("## 5. Hypothèses et leur origine\n")
    rows = [
        [f"`{name}`", fr(str(value)), PROVENANCE_LABEL[kind], note]
        for name, value in asdict(h).items()
        for kind, note in [finops.PROVENANCE[name]]
    ]
    parts.append(table(["Hypothèse", "Valeur", "Statut", "Origine"], rows))
    parts.append(
        "\nPrix API ($ par million de tokens, prompt ≤ 100 K) : "
        + " ; ".join(
            f"{p.model} {fr(str(p.input_usd_per_mtok))}/{fr(str(p.output_usd_per_mtok))}"
            for p in finops.API_PRICES
        )
        + " (platform.claude.com, vérifié le 05/11/2026).\n"
    )
    return "\n".join(parts)


PROVENANCE_LABEL = {"source": "sourcé", "estimation": "estimé", "hypothese": "hypothèse à valider"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measures", default=str(ROOT / "docs/finops/mesures.json"))
    parser.add_argument("--out", default=str(ROOT / "docs/finops/benchmark.md"))
    parser.add_argument("--set", action="append", default=[], metavar="CLE=VALEUR")
    args = parser.parse_args(argv)

    overrides = {}
    for item in args.set:
        key, _, raw = item.partition("=")
        if key not in Hypotheses.__dataclass_fields__:
            print(f"Hypothèse inconnue : {key}", file=sys.stderr)
            return 1
        overrides[key] = type(getattr(Hypotheses(), key))(float(raw))
    h = Hypotheses(**overrides)

    path = Path(args.measures)
    if not path.exists():
        print(f"Mesures absentes : {path} (voir scripts/run_eval.py --json)", file=sys.stderr)
        return 1
    profile = finops.load_profile(path)
    Path(args.out).write_text(render(profile, h, path.name) + "\n")
    print(f"Rapport écrit dans {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
