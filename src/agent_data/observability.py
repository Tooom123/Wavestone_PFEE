"""Observabilite des runs (Langfuse).

Langfuse est optionnel : sans clefs configurees, l'instrumentation se reduit a un journal
local. Un projet qui tourne en local par defaut ne doit pas dependre d'un service externe
pour fonctionner.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field

from agent_data.config import Settings, get_settings


@dataclass
class Span:
    """Mesure d'un noeud du graphe."""

    name: str
    duration_seconds: float
    metadata: dict = field(default_factory=dict)


class Tracer:
    """Instrumente les noeuds de l'agent.

    Envoie vers Langfuse si configure, sinon conserve les mesures en memoire — ce qui
    suffit a repondre a « ou passe le temps d'un run ? ».
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.spans: list[Span] = []
        self._client = self._connect() if self.settings.langfuse_enabled else None

    def _connect(self):  # pragma: no cover - depend d'un service externe
        try:
            from langfuse import Langfuse
        except ImportError:
            return None
        try:
            return Langfuse(
                public_key=self.settings.langfuse_public_key,
                secret_key=self.settings.langfuse_secret_key,
                host=self.settings.langfuse_host,
            )
        except Exception:  # noqa: BLE001 - l'observabilite ne doit jamais casser un run
            return None

    @contextmanager
    def span(self, name: str, **metadata: object) -> Iterator[None]:
        """Mesure la duree d'un bloc."""
        started = time.monotonic()
        try:
            yield
        finally:
            duration = time.monotonic() - started
            self.spans.append(Span(name=name, duration_seconds=duration, metadata=dict(metadata)))
            if self._client is not None:  # pragma: no cover
                # L'observabilite ne doit jamais faire echouer un run.
                with suppress(Exception):
                    self._client.trace(name=name, metadata={**metadata, "duration": duration})

    def summary(self) -> str:
        """Resume lisible du temps passe par noeud."""
        if not self.spans:
            return "(aucune mesure)"
        total = sum(s.duration_seconds for s in self.spans)
        lines = [f"Duree totale : {total:.1f}s"]
        for span in self.spans:
            share = span.duration_seconds / total if total else 0
            lines.append(f"  {span.name:16} {span.duration_seconds:6.1f}s ({share:.0%})")
        return "\n".join(lines)
