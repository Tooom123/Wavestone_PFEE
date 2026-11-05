"""Catalogue de GPU et estimations de debit."""

from __future__ import annotations

from agent_data.gpu_catalog import (
    CATALOG,
    REFERENCE,
    comparison,
    estimate_tokens_per_second,
    fits,
)

QWEN, GEMMA = 8.99, 9.61  # Go, tailles Ollama


def test_la_reference_est_la_4070_super() -> None:
    assert REFERENCE.name == "RTX 4070 SUPER" and REFERENCE.vram_gb == 12


def test_les_deux_modeles_tiennent_sur_12_go() -> None:
    assert fits(REFERENCE, QWEN) and fits(REFERENCE, GEMMA)


def test_un_modele_de_30_go_ne_tient_pas_sur_12_go_mais_tient_sur_48() -> None:
    l40s = next(g for g in CATALOG if g.key == "l40s")
    assert not fits(REFERENCE, 18.6)  # qwen3-coder:30b, ecarte dans le README
    assert fits(l40s, 18.6)


def test_le_debit_de_reference_est_la_mesure_elle_meme() -> None:
    assert estimate_tokens_per_second(REFERENCE, "qwen2.5-coder:14b") == 37.4


def test_le_debit_estime_suit_la_bande_passante() -> None:
    h100 = next(g for g in CATALOG if g.key == "h100")
    estime = estimate_tokens_per_second(h100, "qwen2.5-coder:14b")
    assert estime is not None and estime == round(37.4 * 3350 / 504.2, 1)


def test_modele_inconnu_pas_d_estimation() -> None:
    assert estimate_tokens_per_second(REFERENCE, "modele-inconnu") is None


def test_comparison_ne_donne_pas_de_debit_si_ca_ne_tient_pas() -> None:
    rows = comparison({"gros": 40.0})
    petit = next(r for r in rows if r["key"] == "rtx4070s")
    assert petit["models"]["gros"] == {"fits": False, "tokens_per_second": None}
    assert sum(r["is_reference"] for r in rows) == 1
