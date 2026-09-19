"""Tests de la configuration."""

import pytest
from pydantic import ValidationError

from agent_data.config import Settings


def test_defauts_sur_llm_local() -> None:
    """Par defaut rien ne sort du poste : c'est l'option la moins engageante."""
    s = Settings(_env_file=None)
    assert s.is_local_llm
    assert s.human_validation is True


def test_provider_inconnu_rejete() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="mistral-cloud")


def test_provider_distant_non_local() -> None:
    assert not Settings(_env_file=None, llm_provider="anthropic").is_local_llm


def test_langfuse_desactive_sans_clefs() -> None:
    assert not Settings(_env_file=None).langfuse_enabled
    configured = Settings(_env_file=None, langfuse_public_key="a", langfuse_secret_key="b")
    assert configured.langfuse_enabled
