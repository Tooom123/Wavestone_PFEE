"""Acces au LLM.

Le fournisseur par defaut est **Ollama, en local** : le profil des donnees ne quitte pas
le poste. Le choix reste ouvert cote Wavestone, donc l'interface est identique pour un
fournisseur distant : changer `LLM_PROVIDER` suffit, sans toucher au code appelant.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Protocol

from agent_data.config import Role, Settings, get_settings


class LLMError(RuntimeError):
    """Echec d'un appel au LLM."""


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

    def is_available(self) -> bool:
        """Vrai si le serveur Ollama repond."""
        try:
            with urllib.request.urlopen(  # noqa: S310  # nosec B310 - schema http(s) valide par Settings
                f"{self.settings.llm_base_url}/api/version", timeout=5
            ) as response:
                return response.status == 200
        except (urllib.error.URLError, OSError, TimeoutError):
            return False

    def installed_models(self) -> list[str]:
        """Liste les modeles presents sur le serveur."""
        try:
            with urllib.request.urlopen(  # noqa: S310  # nosec B310 - schema http(s) valide par Settings
                f"{self.settings.llm_base_url}/api/tags", timeout=10
            ) as response:
                payload = json.loads(response.read())
        except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError):
            return []
        return [m.get("name", "") for m in payload.get("models", [])]

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
