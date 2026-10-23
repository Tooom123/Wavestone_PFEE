"""Configuration du projet, lue depuis l'environnement (fichier `.env`).

Les valeurs par defaut correspondent aux choix les moins engageants : LLM **local**
(aucune donnee ne sort du poste), validation humaine du plan activee, plafonds bas.
Tout se surcharge par variable d'environnement, sans toucher au code.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"

Role = Literal["planner", "coder", "critic", "synthesis"]
"""Les quatre taches de l'agent, chacune pouvant etre servie par son propre modele."""


class Settings(BaseSettings):
    """Parametres d'execution de l'agent."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM ---------------------------------------------------------------
    llm_provider: str = Field(default="ollama", description="ollama | anthropic | openai")
    llm_model: str = Field(default="qwen2.5-coder:14b")
    llm_base_url: str = Field(default="http://localhost:11434")
    # Un modele par role. Vide = retombe sur `llm_model`. Un 14B code bien mais raisonne et
    # redige moins bien qu'il ne code ; un petit modele suffit pour relire un resultat.
    planner_model: str = Field(default="", description="Question metier -> plan d'analyse")
    coder_model: str = Field(default="", description="Plan -> code Python")
    critic_model: str = Field(default="", description="Relecture des resultats")
    synthesis_model: str = Field(default="", description="Artefacts -> reponse en francais")
    llm_keep_alive: str = Field(
        default="10m", description="Duree de maintien d'un modele en VRAM entre deux appels"
    )
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    llm_timeout_seconds: int = Field(default=180, gt=0)
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # --- Garde-fous du run -------------------------------------------------
    max_iterations: int = Field(default=5, ge=1)
    max_tokens_budget: int = Field(default=200_000, gt=0)
    human_validation: bool = Field(
        default=True, description="Validation humaine du plan au premier passage"
    )

    # --- Sandbox -----------------------------------------------------------
    sandbox_image: str = Field(default="agent-data-sandbox:latest")
    sandbox_timeout_seconds: int = Field(default=60, gt=0)
    sandbox_memory_limit: str = Field(default="2g")
    sandbox_cpus: float = Field(default=2.0, gt=0)

    # --- API de demonstration ----------------------------------------------
    api_token: str = Field(
        default="", description="Jeton exige par l'API. Obligatoire des qu'elle est exposee."
    )
    api_cors_origins: str = Field(
        default="http://localhost:3000",
        description="Origines autorisees a appeler l'API, separees par des virgules",
    )

    # --- Observabilite -----------------------------------------------------
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    @field_validator("llm_provider")
    @classmethod
    def _known_provider(cls, v: str) -> str:
        known = {"ollama", "anthropic", "openai"}
        if v not in known:
            raise ValueError(f"llm_provider doit etre l'un de {sorted(known)}, recu : {v!r}")
        return v

    def model_for(self, role: Role) -> str:
        """Modele a utiliser pour `role`, ou le modele par defaut."""
        return getattr(self, f"{role}_model") or self.llm_model

    @property
    def is_local_llm(self) -> bool:
        """Vrai quand aucun appel ne sort du poste."""
        return self.llm_provider == "ollama"

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    """Retourne les parametres (memoises pour tout le process)."""
    return Settings()
