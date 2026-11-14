"""Verrou des modeles : condensats, ecarts, et porte d'entree du golden dataset."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_data import model_lock
from agent_data.cli import main as cli_main
from agent_data.config import ROLES, Settings

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = Settings(
    _env_file=None,  # type: ignore[call-arg]
    planner_model="gemma4:e4b",
    coder_model="qwen2.5-coder:14b",
    critic_model="qwen2.5-coder:14b",
    synthesis_model="gemma4:e4b",
)


def _tag(name: str, digest: str) -> dict:
    return {"name": name, "digest": digest, "details": {"parameter_size": "8B"}}


TAGS = [_tag("gemma4:e4b", "aaa111"), _tag("qwen2.5-coder:14b", "bbb222")]
LOCK = model_lock.build(SETTINGS, TAGS, "0.21.1", None)
GOLDEN = {"passed": 17, "cases": 24, "by_category": {"classement": 4, "hors_perimetre": 0}}


def test_le_verrou_note_le_condensat_de_chaque_role() -> None:
    assert LOCK["roles"]["coder"] == {
        "model": "qwen2.5-coder:14b",
        "digest": "bbb222",
        "parameters": "8B",
        "quantization": "",
    }
    assert set(LOCK["roles"]) == set(ROLES)


def test_conforme() -> None:
    assert model_lock.check(LOCK, SETTINGS, TAGS) == []


def test_meme_nom_nouvelle_version_detectee() -> None:
    pulled = [_tag("gemma4:e4b", "ccc333"), TAGS[1]]
    drifts = model_lock.check(LOCK, SETTINGS, pulled)
    assert {(d.role, d.kind) for d in drifts} == {
        ("planner", "version_changee"),
        ("synthesis", "version_changee"),
    }


def test_modele_change_ou_absent() -> None:
    other = SETTINGS.model_copy(update={"coder_model": "qwen3-coder:14b"})
    tags = [*TAGS, _tag("qwen3-coder:14b", "ddd")]
    assert [d.kind for d in model_lock.check(LOCK, other, tags)] == ["modele_change"]
    assert [d.kind for d in model_lock.check(LOCK, other, TAGS)] == ["absent"]


def test_sans_verrou() -> None:
    [drift] = model_lock.check(None, SETTINGS, TAGS)
    assert drift.kind == "non_fige"


def test_pas_de_regression_la_mise_a_jour_est_permise() -> None:
    better = GOLDEN | {"passed": 20, "by_category": {"classement": 4, "hors_perimetre": 3}}
    assert model_lock.regressions(GOLDEN, better) == []
    assert model_lock.regressions(None, better) == []


def test_une_categorie_qui_baisse_bloque_meme_si_le_total_monte() -> None:
    mixed = GOLDEN | {"passed": 19, "by_category": {"classement": 3, "hors_perimetre": 4}}
    assert model_lock.regressions(GOLDEN, mixed) == ["classement : 3 contre 4"]


def test_total_en_baisse_et_jeu_different() -> None:
    worse = GOLDEN | {"passed": 15}
    assert model_lock.regressions(GOLDEN, worse)[0].startswith("total : 15")
    assert "golden dataset different" in model_lock.regressions(GOLDEN, GOLDEN | {"cases": 30})[0]


RESULTS = {
    "meta": {"date": "2026-11-11", "models": "planner = gemma4:e4b, coder = qwen2.5-coder:14b"},
    "summary": {
        "classement": {"passed": 4},
        "hors_perimetre": {"passed": 0},
        "total": {"passed": 17, "cases": 24},
    },
}


def test_lecture_des_resultats_du_golden() -> None:
    assert model_lock.golden_summary(RESULTS) == GOLDEN | {"date": "2026-11-11"}
    assert model_lock.models_of(RESULTS) == {"planner": "gemma4:e4b", "coder": "qwen2.5-coder:14b"}


def test_le_verrou_du_depot_suit_la_configuration_par_defaut() -> None:
    """models.lock.json et .env.example doivent designer les memes modeles."""
    env = dict(
        line.split("=", 1)
        for line in (ROOT / ".env.example").read_text().splitlines()
        if line.endswith(tuple("0123456789bkm")) and "_MODEL=" in line
    )
    lock = model_lock.load(ROOT / "models.lock.json")
    assert lock is not None and lock["golden"]["cases"] == 24
    for role in ROLES:
        assert lock["roles"][role]["model"] == env[f"{role.upper()}_MODEL"]
        assert len(lock["roles"][role]["digest"]) == 64


# ------------------------------------------------------------------------------- CLI


@pytest.fixture
def poste(monkeypatch, tmp_path: Path) -> Path:
    """Un poste factice : verrou en tmp, Ollama qui sert TAGS, configuration SETTINGS."""
    path = tmp_path / "models.lock.json"
    monkeypatch.setattr(model_lock, "LOCK_PATH", path)
    monkeypatch.setattr("agent_data.cli.get_settings", lambda: SETTINGS)
    monkeypatch.setattr("agent_data.llm.OllamaClient.tags", lambda self: TAGS)
    monkeypatch.setattr("agent_data.llm.OllamaClient.server_version", lambda self: "0.21.1")
    return path


def _run(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr("sys.argv", ["agent-data", *argv])
    with pytest.raises(SystemExit) as exit_:
        cli_main()
    return int(exit_.value.code or 0)


def _results(tmp_path: Path, passed: int, models: str) -> str:
    data = json.loads(json.dumps(RESULTS))
    data["meta"]["models"] = models
    data["summary"]["total"]["passed"] = passed
    path = tmp_path / f"r{passed}.json"
    path.write_text(json.dumps(data))
    return str(path)


ALL = (
    "planner = gemma4:e4b, coder = qwen2.5-coder:14b, "
    "critic = qwen2.5-coder:14b, synthesis = gemma4:e4b"
)


def test_figer_puis_verifier(poste: Path, monkeypatch, tmp_path: Path) -> None:
    assert _run(monkeypatch, "modeles", "figer", "--golden", _results(tmp_path, 17, ALL)) == 0
    assert json.loads(poste.read_text())["golden"]["passed"] == 17
    assert _run(monkeypatch, "modeles", "verifier") == 0
    monkeypatch.setattr(
        "agent_data.llm.OllamaClient.tags", lambda self: [_tag("gemma4:e4b", "x"), TAGS[1]]
    )
    assert _run(monkeypatch, "modeles", "verifier") == 1  # gemma a change sous le meme nom


def test_figer_refuse_une_regression(poste: Path, monkeypatch, tmp_path: Path) -> None:
    _run(monkeypatch, "modeles", "figer", "--golden", _results(tmp_path, 17, ALL))
    assert _run(monkeypatch, "modeles", "figer", "--golden", _results(tmp_path, 15, ALL)) == 1
    assert json.loads(poste.read_text())["golden"]["passed"] == 17  # verrou inchange


def test_figer_refuse_une_evaluation_faite_avec_d_autres_modeles(
    poste: Path, monkeypatch, tmp_path: Path
) -> None:
    other = ALL.replace("coder = qwen2.5-coder:14b", "coder = autre:7b")
    assert _run(monkeypatch, "modeles", "figer", "--golden", _results(tmp_path, 20, other)) == 1
    assert not poste.exists()
