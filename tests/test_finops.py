"""Tests du modele de couts, sur des chiffres calculables a la main."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_data import finops
from agent_data.finops import ApiPrice, Hypotheses, Profile

PROFILE = Profile(seconds=120.0, prompt_tokens=20_000, completion_tokens=5_000, gpu_energy_wh=10.0)


def test_cout_api_est_tokens_fois_prix() -> None:
    h = Hypotheses(usd_to_eur=1.0, ops_hours_api=0)
    scenario = finops.api(PROFILE, h, ApiPrice("Claude Test 1", 2.0, 10.0))
    # 20 000 x 2 $/M + 5 000 x 10 $/M = 0,04 + 0,05
    assert scenario.variable_total == pytest.approx(0.09)
    assert scenario.fixed_total == 0


def test_electricite_inclut_le_gpu_et_le_poste() -> None:
    h = Hypotheses(electricity_eur_per_kwh=1.0, host_power_w=120.0)
    scenario = finops.on_premise(PROFILE, h)
    # 10 Wh de GPU + 120 W pendant 120 s (= 4 Wh) = 14 Wh = 0,014 kWh
    assert scenario.variable["électricité"] == pytest.approx(0.014)


def test_amortissement_mensuel() -> None:
    h = Hypotheses(workstation_capex_eur=3600, amortization_months=36, ops_hours_onprem=0)
    assert finops.on_premise(PROFILE, h).fixed["amortissement"] == pytest.approx(100)


def test_capacite_du_poste_local() -> None:
    h = Hypotheses(utilization=0.5)
    capacity = finops.on_premise(PROFILE, h).capacity_runs
    # 730 h x 3 600 s x 50 % / 120 s par run
    assert capacity == pytest.approx(730 * 3600 * 0.5 / 120)


def test_un_gpu_plus_rapide_absorbe_plus_de_runs() -> None:
    h = Hypotheses()
    cap = {s.key: s.capacity_runs for s in finops.scenarios(PROFILE, h)}
    assert cap["h100-24-7"] > cap["l40s-24-7"] > cap["onprem"]
    assert cap["l40s-bureau"] < cap["l40s-24-7"]


def test_une_api_n_a_pas_de_limite_de_capacite() -> None:
    api = next(s for s in finops.scenarios(PROFILE) if s.key.startswith("api-"))
    assert api.capacity_runs is None and api.feasible(10**9)


def test_point_mort_entre_poste_local_et_api() -> None:
    h = Hypotheses()
    local = finops.on_premise(PROFILE, h)
    sonnet = finops.api(PROFILE, h, finops.API_PRICES[1])
    runs = finops.break_even_runs(local, sonnet)
    # Le poste a une part fixe plus haute et une part variable plus basse : il gagne
    # au-dela d'un volume, et les deux couts mensuels y sont egaux.
    assert runs is not None and runs > 0
    assert local.monthly(runs) == pytest.approx(sonnet.monthly(runs))


def test_pas_de_point_mort_si_un_mode_domine() -> None:
    cheap = finops.Scenario("a", "a", fixed={"x": 1}, variable={"y": 0.1})
    dear = finops.Scenario("b", "b", fixed={"x": 5}, variable={"y": 0.5})
    assert finops.break_even_runs(cheap, dear) is None  # `cheap` gagne partout


def test_la_sensibilite_fait_varier_une_seule_hypothese() -> None:
    rows = finops.sensitivity(PROFILE, Hypotheses(), "electricity_eur_per_kwh", (1.0, 2.0), 1000)
    base, double = rows[0]["unit_costs"], rows[1]["unit_costs"]
    assert double["onprem"] > base["onprem"]
    assert double["api-haiku"] == pytest.approx(base["api-haiku"])  # l'API ignore l'electricite


def test_chaque_hypothese_a_une_origine() -> None:
    assert set(finops.PROVENANCE) == set(Hypotheses.__dataclass_fields__)


def test_profil_moyenne_des_cas_mesures(tmp_path: Path) -> None:
    def case(seconds: float, p: int, c: int, wh: float) -> dict:
        usage = {"coder": {"prompt_tokens": p, "completion_tokens": c}}
        return {"seconds": seconds, "usage": usage, "gpu": {"energy_wh": wh}}

    path = tmp_path / "mesures.json"
    path.write_text(json.dumps([case(100, 1000, 100, 8), case(200, 3000, 300, 12)]))
    profile = finops.load_profile(path)
    assert (profile.seconds, profile.prompt_tokens, profile.completion_tokens) == (150, 2000, 200)
    assert profile.gpu_energy_wh == 10


def test_profil_sans_mesure_refuse(tmp_path: Path) -> None:
    path = tmp_path / "vide.json"
    path.write_text("[]")
    with pytest.raises(ValueError):
        finops.load_profile(path)
