"""Tests de l'API de demonstration, sans LLM ni Docker reels."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_data.api import create_app
from agent_data.api.runs import RunManager
from agent_data.config import Settings
from agent_data.graph import Stage1
from agent_data.schemas import ExecutionResult
from tests.conftest import FakeLLM, FakeSandbox

CODE = "```python\nprint('ok')\n```"
SATISFIED = '{"is_satisfactory": true, "issues": []}'


@pytest.fixture
def data_dir(tmp_path: Path, csv_ventes: Path) -> Path:
    folder = tmp_path / "data" / "ventes"
    folder.mkdir(parents=True)
    (folder / "ventes.csv").write_text(csv_ventes.read_text())
    return tmp_path / "data"


def _client(
    data_dir: Path, llm: FakeLLM, results: list[ExecutionResult], **settings: object
) -> TestClient:
    base = Settings(_env_file=None, **settings)  # type: ignore[arg-type]
    manager = RunManager(lambda: Stage1(settings=base, client=llm, sandbox=FakeSandbox(results)))  # type: ignore[arg-type]
    return TestClient(create_app(settings=base, manager=manager, data_dir=data_dir))


def _events(client: TestClient, run_id: str, headers: dict | None = None) -> list[dict]:
    with client.stream("GET", f"/api/runs/{run_id}/events", headers=headers or {}) as response:
        return [
            json.loads(line.removeprefix("data: "))
            for line in response.iter_lines()
            if line.startswith("data: ")
        ]


def test_liste_des_datasets(data_dir: Path) -> None:
    client = _client(data_dir, FakeLLM([]), [])
    [dataset] = client.get("/api/datasets").json()
    assert dataset["name"] == "ventes"
    assert dataset["rows"] == 4
    assert {c["name"] for c in dataset["columns"]} >= {"montant", "region"}


def test_run_complet_en_streaming(data_dir: Path, plan_json: str, ok_result) -> None:
    llm = FakeLLM([plan_json, CODE, SATISFIED, "Le chiffre d'affaires a progresse de 100."])
    client = _client(data_dir, llm, [ok_result], human_validation=False)

    body = {"question": "Les ventes sont-elles bonnes ?", "datasets": ["ventes"]}
    run_id = client.post("/api/runs", json=body | {"validate_plan": False}).json()["run_id"]
    events = _events(client, run_id)

    kinds = [e["kind"] for e in events]
    assert kinds[0] == "start" and kinds[-1] == "done"
    assert {"profile", "plan", "iteration", "code", "execution", "critique"} <= set(kinds)
    assert [e["i"] for e in events] == list(range(len(events)))  # ordre stable, reprise possible
    done = events[-1]
    assert set(done["metrics"]["usage"]) == {"planner", "coder", "critic", "synthesis"}
    assert "energy_wh" in done["metrics"]["gpu"]
    assert "progresse" in done["report"]["synthesis"]
    assert done["report"]["artifacts"]


def test_validation_du_plan_bloque_jusqu_a_la_decision(data_dir: Path, plan_json: str) -> None:
    llm = FakeLLM([plan_json])
    client = _client(data_dir, llm, [])
    run_id = client.post(
        "/api/runs",
        json={"question": "Une question", "datasets": ["ventes"], "validate_plan": True},
    ).json()["run_id"]

    client.post(f"/api/runs/{run_id}/approval", json={"approved": False})
    events = _events(client, run_id)

    kinds = [e["kind"] for e in events]
    assert "awaiting_approval" in kinds
    assert "code" not in kinds  # plan refuse : rien n'a ete genere ni execute
    assert events[-1]["kind"] == "done"
    assert any("refuse" in e for e in events[-1]["errors"])


def test_dataset_inconnu_refuse(data_dir: Path) -> None:
    client = _client(data_dir, FakeLLM([]), [])
    response = client.post("/api/runs", json={"question": "Une question", "datasets": ["../etc"]})
    assert response.status_code == 404


def test_jeton_exige_quand_configure(data_dir: Path) -> None:
    client = _client(data_dir, FakeLLM([]), [], api_token="secret")
    assert client.get("/api/datasets").status_code == 401
    assert client.get("/api/datasets", headers={"Authorization": "Bearer faux"}).status_code == 401
    assert (
        client.get("/api/datasets", headers={"Authorization": "Bearer secret"}).status_code == 200
    )
    assert client.get("/api/health").status_code == 200  # public : ne revele rien de sensible


def test_un_seul_run_a_la_fois(data_dir: Path, plan_json: str) -> None:
    client = _client(data_dir, FakeLLM([plan_json]), [])
    body = {"question": "Une question", "datasets": ["ventes"], "validate_plan": True}
    first = client.post("/api/runs", json=body)
    assert first.status_code == 200
    assert client.post("/api/runs", json=body).status_code == 409
    client.post(f"/api/runs/{first.json()['run_id']}/approval", json={"approved": False})


def test_endpoint_systeme_donne_le_gpu_et_la_comparaison(data_dir: Path) -> None:
    client = _client(data_dir, FakeLLM([]), [])
    body = client.get("/api/system").json()
    assert {"gpu", "live", "models", "catalog"} <= set(body)
    assert any(row["is_reference"] for row in body["catalog"])
