"""Catalogue de GPU pour situer le materiel de l'agent par rapport aux alternatives.

Les caracteristiques viennent des fiches des constructeurs et de sites de reference ; chaque
entree dit d'ou vient son prix. Les debits des autres GPU sont des **estimations**, pas des
mesures : le decodage d'un LLM etant limite par la bande passante memoire, on extrapole le
debit mesure sur notre GPU proportionnellement a la bande passante de l'autre.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class GpuSpec:
    key: str
    name: str
    vram_gb: int
    memory: str
    bandwidth_gbs: float
    power_w: int
    segment: str  # "poste" ou "datacenter"
    price_note: str
    cloud_eur_per_hour: float | None = None
    cloud_source: str = ""


CATALOG: list[GpuSpec] = [
    GpuSpec(
        "rtx4070s",
        "RTX 4070 SUPER",
        12,
        "GDDR6X",
        504.2,
        220,
        "poste",
        "Lancement : 599 $ / 659 € TTC (prix actuels a verifier : le marche a monte en 2026)",
    ),
    GpuSpec(
        "rtx4090",
        "RTX 4090",
        24,
        "GDDR6X",
        1008.0,
        450,
        "poste",
        "Prix actuel non verifie",
    ),
    GpuSpec(
        "rtx5090",
        "RTX 5090",
        32,
        "GDDR7",
        1792.0,
        575,
        "poste",
        "Prix actuel non verifie (forte hausse signalee en 2026)",
    ),
    GpuSpec(
        "l40s",
        "L40S",
        48,
        "GDDR6",
        864.0,
        350,
        "datacenter",
        "Location cloud",
        1.40,
        "Scaleway, 1x L40S, € HT/h (grille officielle)",
    ),
    GpuSpec(
        "a100",
        "A100 80 Go (SXM4)",
        80,
        "HBM2e",
        2039.0,
        400,
        "datacenter",
        "Prix non verifie",
    ),
    GpuSpec(
        "h100",
        "H100 80 Go (SXM)",
        80,
        "HBM3",
        3350.0,
        700,
        "datacenter",
        "Location cloud",
        2.73,
        "Scaleway, 1x H100, € HT/h (grille officielle)",
    ),
]

REFERENCE = CATALOG[0]
"""GPU sur lequel les debits ci-dessous ont ete mesures."""

MEASURED_TOKENS_PER_SECOND: dict[str, float] = {
    # Mesure du 05/11/2026 : RTX 4070 SUPER, Ollama 0.21.1, temperature 0, 300 tokens generes.
    "qwen2.5-coder:14b": 37.4,
    "gemma4:e4b": 82.3,
}

#: Memoire reservee au cache de contexte et au runtime, en plus des poids du modele.
OVERHEAD_GB = 1.5


def fits(spec: GpuSpec, model_gb: float) -> bool:
    """Vrai si le modele (poids + cache de contexte) tient entierement en VRAM."""
    return model_gb + OVERHEAD_GB <= spec.vram_gb


def estimate_tokens_per_second(spec: GpuSpec, model: str) -> float | None:
    """Debit de decodage estime sur `spec`, extrapole de la mesure sur le GPU de reference."""
    measured = MEASURED_TOKENS_PER_SECOND.get(model)
    if measured is None:
        return None
    return round(measured * spec.bandwidth_gbs / REFERENCE.bandwidth_gbs, 1)


def comparison(model_sizes_gb: dict[str, float]) -> list[dict]:
    """Une ligne par GPU : ce qui tient, a quelle vitesse (estimee), pour quel prix."""
    rows = []
    for spec in CATALOG:
        models = {}
        for model, size in model_sizes_gb.items():
            ok = fits(spec, size)
            models[model] = {
                "fits": ok,
                "tokens_per_second": estimate_tokens_per_second(spec, model) if ok else None,
            }
        rows.append(
            {
                **asdict(spec),
                "is_reference": spec.key == REFERENCE.key,
                "models": models,
                # Regle empirique : ~0,6 Go par milliard de parametres en Q4, moins l'overhead.
                "max_params_b": max(0, round((spec.vram_gb - OVERHEAD_GB) / 0.6)),
            }
        )
    return rows
