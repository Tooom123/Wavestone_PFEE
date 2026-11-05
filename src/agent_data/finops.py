"""Modele de couts : agent local (on-premise) contre GPU loue contre API de LLM.

Le modele ne contient aucun chiffre cache. Chaque hypothese est un champ de `Hypotheses`
avec son origine dans `PROVENANCE` : `source` (prix publie, verifie a la date indiquee) ou
`hypothese` (valeur de travail a remplacer par la realite de Wavestone). Un resultat n'est
donc jamais plus fiable que ses hypotheses les plus fragiles, et le rapport le dit.

Les mesures (tokens, energie, duree) viennent de vrais runs : `scripts/run_eval.py --json`.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

HOURS_PER_MONTH = 730.0  # 8 760 h / 12


@dataclass(frozen=True)
class Profile:
    """Ce que coute un run moyen, mesure sur le materiel de reference."""

    seconds: float
    prompt_tokens: float
    completion_tokens: float
    gpu_energy_wh: float
    reference_bandwidth_gbs: float = 504.2  # RTX 4070 SUPER


def load_profile(path: Path) -> Profile:
    """Moyenne des cas mesures par `scripts/run_eval.py --json`."""
    cases = json.loads(path.read_text())
    if not cases:
        raise ValueError(f"Aucune mesure dans {path}")
    n = len(cases)

    def mean(values: list[float]) -> float:
        return sum(values) / n

    return Profile(
        seconds=mean([c["seconds"] for c in cases]),
        prompt_tokens=mean([sum(u["prompt_tokens"] for u in c["usage"].values()) for c in cases]),
        completion_tokens=mean(
            [sum(u["completion_tokens"] for u in c["usage"].values()) for c in cases]
        ),
        gpu_energy_wh=mean([c["gpu"]["energy_wh"] for c in cases]),
    )


@dataclass(frozen=True)
class Hypotheses:
    # --- Electricite et poste local
    electricity_eur_per_kwh: float = 0.1624
    host_power_w: float = 120.0  # reste du poste pendant un run (CPU, RAM, ventilation)
    workstation_capex_eur: float = 1700.0  # GPU + reste de la machine
    amortization_months: int = 36
    # --- GPU loue
    l40s_eur_per_hour: float = 1.40
    h100_eur_per_hour: float = 2.73
    l40s_speedup: float = 1.71  # 864 / 504,2 Go/s : estimation, pas une mesure
    h100_speedup: float = 6.64  # 3 350 / 504,2 Go/s : estimation, pas une mesure
    office_hours_per_month: float = 176.0  # 8 h x 22 jours
    # --- API de LLM (USD par million de tokens)
    usd_to_eur: float = 0.86
    # --- Exploitation (en heures par mois)
    ops_hours_onprem: float = 4.0
    ops_hours_cloud_gpu: float = 3.0
    ops_hours_api: float = 1.0
    ops_eur_per_hour: float = 60.0
    # --- Taux d'occupation maximal retenu pour la capacite
    utilization: float = 0.5


PROVENANCE: dict[str, tuple[str, str]] = {
    "electricity_eur_per_kwh": (
        "source",
        "Tarif Bleu Pro, ~0,1624 EUR/kWh HT (Selectra, août 2026) ; les sources divergent "
        "(0,25 EUR/kWh HT pour les petits professionnels au S1 2026)",
    ),
    "host_power_w": ("hypothese", "Puissance du poste hors GPU pendant un run, non mesurée"),
    "workstation_capex_eur": (
        "hypothese",
        "659 EUR TTC pour la carte au lancement + ~1 000 EUR pour le reste ; prix actuels "
        "non vérifiés (hausse des GPU signalée en 2026)",
    ),
    "amortization_months": ("hypothese", "Durée d'amortissement comptable usuelle d'un poste"),
    "l40s_eur_per_hour": ("source", "Scaleway, tarif public L40S, à l'heure"),
    "h100_eur_per_hour": ("source", "Scaleway, tarif public H100, à l'heure"),
    "l40s_speedup": ("estimation", "Rapport des bandes passantes mémoire, pas une mesure"),
    "h100_speedup": ("estimation", "Rapport des bandes passantes mémoire, pas une mesure"),
    "office_hours_per_month": ("hypothese", "Instance allumée 8 h par jour ouvré"),
    "usd_to_eur": ("hypothese", "Taux de change de travail, à remplacer par le taux du jour"),
    "ops_hours_onprem": (
        "hypothese",
        "Mises à jour de modèles, pilotes, supervision ; à calibrer sur l'exploitation réelle",
    ),
    "ops_hours_cloud_gpu": ("hypothese", "Idem on-premise, plus l'instance à administrer"),
    "ops_hours_api": ("hypothese", "Suivi des versions de modèles et de la facture"),
    "ops_eur_per_hour": ("hypothese", "Coût horaire chargé d'un ingénieur, à remplacer"),
    "utilization": ("hypothese", "Un run à la fois, jamais plus de la moitié du temps"),
}


@dataclass(frozen=True)
class ApiPrice:
    model: str
    input_usd_per_mtok: float
    output_usd_per_mtok: float


# platform.claude.com/docs/en/about-claude/pricing, verifie le 05/11/2026 (prompt <= 100K tokens)
API_PRICES: tuple[ApiPrice, ...] = (
    ApiPrice("Claude Haiku 5.5", 0.10, 0.50),
    ApiPrice("Claude Sonnet 5.5", 2.0, 10.0),
    ApiPrice("Claude Opus 5.5", 4.0, 20.0),
)


@dataclass(frozen=True)
class Scenario:
    """Un mode de deploiement : une part fixe par mois et une part par run."""

    key: str
    label: str
    fixed: dict[str, float] = field(default_factory=dict)  # EUR / mois
    variable: dict[str, float] = field(default_factory=dict)  # EUR / run
    capacity_runs: float | None = None  # runs par mois que la machine peut absorber

    @property
    def fixed_total(self) -> float:
        return sum(self.fixed.values())

    @property
    def variable_total(self) -> float:
        return sum(self.variable.values())

    def monthly(self, runs: float) -> float:
        return self.fixed_total + self.variable_total * runs

    def unit(self, runs: float) -> float:
        return self.monthly(runs) / runs

    def feasible(self, runs: float) -> bool:
        return self.capacity_runs is None or runs <= self.capacity_runs


def _capacity(profile: Profile, hours: float, speedup: float, utilization: float) -> float:
    return hours * 3600 * utilization / (profile.seconds / speedup)


def on_premise(profile: Profile, h: Hypotheses) -> Scenario:
    energy_kwh = (profile.gpu_energy_wh + h.host_power_w * profile.seconds / 3600) / 1000
    return Scenario(
        key="onprem",
        label="Poste local (RTX 4070 SUPER)",
        fixed={
            "amortissement": h.workstation_capex_eur / h.amortization_months,
            "exploitation": h.ops_hours_onprem * h.ops_eur_per_hour,
        },
        variable={"électricité": energy_kwh * h.electricity_eur_per_kwh},
        capacity_runs=_capacity(profile, HOURS_PER_MONTH, 1.0, h.utilization),
    )


def cloud_gpu(
    profile: Profile,
    h: Hypotheses,
    *,
    key: str,
    label: str,
    eur_per_hour: float,
    speedup: float,
    hours: float,
) -> Scenario:
    return Scenario(
        key=key,
        label=label,
        fixed={
            "instance": eur_per_hour * hours,
            "exploitation": h.ops_hours_cloud_gpu * h.ops_eur_per_hour,
        },
        capacity_runs=_capacity(profile, hours, speedup, h.utilization),
    )


def api(profile: Profile, h: Hypotheses, price: ApiPrice) -> Scenario:
    usd = (
        profile.prompt_tokens * price.input_usd_per_mtok
        + profile.completion_tokens * price.output_usd_per_mtok
    ) / 1e6
    return Scenario(
        key=f"api-{price.model.split()[1].lower()}",
        label=f"API {price.model}",
        fixed={"exploitation": h.ops_hours_api * h.ops_eur_per_hour},
        variable={"tokens": usd * h.usd_to_eur},
    )


def scenarios(profile: Profile, h: Hypotheses | None = None) -> list[Scenario]:
    h = h or Hypotheses()
    out = [
        on_premise(profile, h),
        cloud_gpu(
            profile,
            h,
            key="l40s-bureau",
            label="GPU loué L40S, heures ouvrées",
            eur_per_hour=h.l40s_eur_per_hour,
            speedup=h.l40s_speedup,
            hours=h.office_hours_per_month,
        ),
        cloud_gpu(
            profile,
            h,
            key="l40s-24-7",
            label="GPU loué L40S, 24 h/24",
            eur_per_hour=h.l40s_eur_per_hour,
            speedup=h.l40s_speedup,
            hours=HOURS_PER_MONTH,
        ),
        cloud_gpu(
            profile,
            h,
            key="h100-24-7",
            label="GPU loué H100, 24 h/24",
            eur_per_hour=h.h100_eur_per_hour,
            speedup=h.h100_speedup,
            hours=HOURS_PER_MONTH,
        ),
    ]
    out += [api(profile, h, price) for price in API_PRICES]
    return out


def break_even_runs(a: Scenario, b: Scenario) -> float | None:
    """Volume mensuel au-dela duquel `a` coute moins cher que `b` (None si jamais/toujours)."""
    dv = b.variable_total - a.variable_total
    df = a.fixed_total - b.fixed_total
    if math.isclose(dv, 0.0):
        return None
    runs = df / dv
    return runs if runs > 0 else None


def sensitivity(
    profile: Profile, base: Hypotheses, field_name: str, factors: tuple[float, ...], runs: float
) -> list[dict]:
    """Cout unitaire de chaque scenario quand une hypothese varie."""
    value = asdict(base)[field_name]
    rows = []
    for factor in factors:
        varied = Hypotheses(**{**asdict(base), field_name: value * factor})
        rows.append(
            {
                "factor": factor,
                "value": value * factor,
                "unit_costs": {s.key: s.unit(runs) for s in scenarios(profile, varied)},
            }
        )
    return rows
