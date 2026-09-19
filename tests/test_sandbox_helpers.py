"""Tests des helpers embarques dans l'image du sandbox.

Ces modules vivent sous `docker/` car ils sont installes dans l'image, pas dans le
paquet. Ils sont testes ici car ce sont eux qui garantissent que les artefacts produits
par le code genere respectent le contrat inter-etages.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from agent_data.sandbox import DockerSandbox

DOCKER_DIR = Path(__file__).resolve().parents[1] / "docker"


def _load(name: str, monkeypatch: pytest.MonkeyPatch, out_dir: Path):
    """Charge un module de `docker/` avec sa zone de sortie redirigee."""
    monkeypatch.setenv("AGENT_OUT_DIR", str(out_dir))
    spec = importlib.util.spec_from_file_location(name, DOCKER_DIR / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_save_table_produit_un_artefact_valide(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent_out = _load("agent_out", monkeypatch, tmp_path)
    df = pd.DataFrame({"categorie": ["a", "b"], "marge": [1.5, 2.5]})

    agent_out.save_table(df, "Marges", step_id="s1")

    artifacts = DockerSandbox._collect_artifacts(tmp_path)
    assert len(artifacts) == 1
    assert artifacts[0].payload.kind == "table"
    assert artifacts[0].payload.columns == ["categorie", "marge"]
    assert artifacts[0].payload.rows == [["a", 1.5], ["b", 2.5]]


def test_save_finding_produit_un_artefact_valide(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent_out = _load("agent_out", monkeypatch, tmp_path)

    agent_out.save_finding("Furniture est la moins rentable", evidence="68 EUR", confidence=0.9)

    artifacts = DockerSandbox._collect_artifacts(tmp_path)
    assert artifacts[0].payload.kind == "finding"
    assert artifacts[0].payload.confidence == pytest.approx(0.9)


def test_save_figure_produit_un_artefact_valide(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent_out = _load("agent_out", monkeypatch, tmp_path)

    agent_out.save_figure({"data": [], "layout": {}}, "Courbe")

    artifacts = DockerSandbox._collect_artifacts(tmp_path)
    assert artifacts[0].payload.kind == "figure"


def test_types_numpy_convertis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Le code genere manipule des types numpy : ils doivent passer en JSON."""
    agent_out = _load("agent_out", monkeypatch, tmp_path)
    df = pd.DataFrame({"n": pd.Series([1, 2], dtype="int64"), "x": [1.5, 2.5]})

    agent_out.save_table(df, "T")

    artifacts = DockerSandbox._collect_artifacts(tmp_path)
    assert artifacts[0].payload.rows == [[1, 1.5], [2, 2.5]]


def test_table_tronquee(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    agent_out = _load("agent_out", monkeypatch, tmp_path)

    agent_out.save_table(pd.DataFrame({"x": range(1000)}), "T", max_rows=10)

    assert len(DockerSandbox._collect_artifacts(tmp_path)[0].payload.rows) == 10


def test_plusieurs_artefacts_ne_s_ecrasent_pas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent_out = _load("agent_out", monkeypatch, tmp_path)

    agent_out.save_finding("un")
    agent_out.save_finding("deux")

    assert len(DockerSandbox._collect_artifacts(tmp_path)) == 2


def test_encodeur_json_tolere_numpy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """sitecustomize rend json.dump tolerant aux types numpy."""
    import numpy as np

    _load("sitecustomize", monkeypatch, tmp_path)
    blob = json.dumps({"a": np.int64(5), "b": np.float64(1.5), "c": np.array([1, 2])})
    assert json.loads(blob) == {"a": 5, "b": 1.5, "c": [1, 2]}
