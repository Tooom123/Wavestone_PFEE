"""Acces au LLM.

Le fournisseur par defaut est **Ollama, en local** : le profil des donnees ne quitte pas
le poste. Le choix reste ouvert cote Wavestone, donc l'interface est identique pour un
fournisseur distant : changer `LLM_PROVIDER` suffit, sans toucher au code appelant.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from agent_data.config import Role, Settings, get_settings


class LLMError(RuntimeError):
    """Echec d'un appel au LLM."""


@dataclass
class Usage:
    """Consommation cumulee d'un client : ce que coute reellement un run en tokens et en temps."""

    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    load_seconds: float = 0.0
    """Part passee a charger le modele en VRAM (changement de modele)."""

    def add(self, other: Usage) -> None:
        self.calls += other.calls
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.seconds += other.seconds
        self.load_seconds += other.load_seconds

    def as_dict(self) -> dict[str, float | int]:
        return {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "seconds": round(self.seconds, 1),
            "load_seconds": round(self.load_seconds, 1),
        }


class LLMClient(Protocol):
    """Interface minimale attendue par le planificateur et l'executeur."""

    def complete(self, prompt: str, *, system: str = "") -> str:
        """Retourne la reponse du modele pour `prompt`."""
        ...


class OllamaClient:
    """Client HTTP pour un serveur Ollama local.

    Appel direct de l'API REST plutot que du SDK : une dependance en moins pour un
    unique point d'entree, et le format de requete d'Ollama est stable.
    """

    def __init__(self, settings: Settings | None = None, *, model: str | None = None) -> None:
        self.settings = settings or get_settings()
        self.model = model or self.settings.llm_model
        self.usage = Usage()

    def is_available(self) -> bool:
        """Vrai si le serveur Ollama repond."""
        try:
            with urllib.request.urlopen(  # noqa: S310  # nosec B310 - schema http(s) valide par Settings
                f"{self.settings.llm_base_url}/api/version", timeout=5
            ) as response:
                return response.status == 200
        except (urllib.error.URLError, OSError, TimeoutError):
            return False

    def tags(self) -> list[dict]:
        """Modeles presents sur le serveur, tels que les decrit Ollama (nom, condensat, taille)."""
        try:
            with urllib.request.urlopen(  # noqa: S310  # nosec B310 - schema http(s) valide par Settings
                f"{self.settings.llm_base_url}/api/tags", timeout=10
            ) as response:
                payload = json.loads(response.read())
        except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError):
            return []
        return list(payload.get("models", []))

    def server_version(self) -> str:
        """Version du serveur Ollama, ou chaine vide s'il ne repond pas."""
        try:
            with urllib.request.urlopen(  # noqa: S310  # nosec B310 - schema http(s) valide par Settings
                f"{self.settings.llm_base_url}/api/version", timeout=5
            ) as response:
                return str(json.loads(response.read()).get("version", ""))
        except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError):
            return ""

    def installed_models(self) -> list[str]:
        """Liste les modeles presents sur le serveur."""
        return [m.get("name", "") for m in self.tags()]

    def model_sizes_gb(self) -> dict[str, float]:
        """Taille sur disque de chaque modele installe, en Go."""
        return {m.get("name", ""): m.get("size", 0) / 1e9 for m in self.tags()}

    def complete(self, prompt: str, *, system: str = "") -> str:
        """Interroge le modele et retourne sa reponse textuelle."""
        body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self.settings.llm_keep_alive,
            "options": {"temperature": self.settings.llm_temperature},
        }
        if system:
            body["system"] = system

        request = urllib.request.Request(  # noqa: S310  # nosec B310 - schema http(s) valide par Settings
            f"{self.settings.llm_base_url}/api/generate",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(  # noqa: S310  # nosec B310 - schema http(s) valide par Settings
                request, timeout=self.settings.llm_timeout_seconds
            ) as response:
                payload = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            raise LLMError(f"Ollama a repondu {exc.code} : {exc.read()[:500]!r}") from exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise LLMError(
                f"Serveur Ollama injoignable sur {self.settings.llm_base_url}. "
                "Demarrer `ollama serve` puis relancer."
            ) from exc
        except json.JSONDecodeError as exc:
            raise LLMError("Reponse Ollama illisible (JSON invalide).") from exc

        # Ollama renvoie les compteurs de tokens et les durees (en nanosecondes).
        self.usage.add(
            Usage(
                calls=1,
                prompt_tokens=int(payload.get("prompt_eval_count", 0)),
                completion_tokens=int(payload.get("eval_count", 0)),
                seconds=payload.get("total_duration", 0) / 1e9,
                load_seconds=payload.get("load_duration", 0) / 1e9,
            )
        )
        return str(payload.get("response", "")).strip()


def get_client(settings: Settings | None = None, role: Role | None = None) -> LLMClient:
    """Retourne le client du fournisseur configure, branche sur le modele du `role`."""
    settings = settings or get_settings()
    if settings.llm_provider == "ollama":
        return OllamaClient(settings, model=settings.model_for(role) if role else None)
    raise LLMError(
        f"Fournisseur {settings.llm_provider!r} non encore implemente. "
        "Le projet tourne en local par defaut (LLM_PROVIDER=ollama)."
    )
