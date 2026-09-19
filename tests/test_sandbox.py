"""Tests du sandbox.

Les tests marques `docker` exigent un daemon Docker et l'image construite ; ils sont
ignores sinon, pour que la CI reste verte sur une machine sans Docker. Ce sont eux qui
verifient reellement l'isolation (reseau coupe, timeout, ecriture interdite) : les lancer
avant toute mise en service du sandbox.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_data.config import Settings
from agent_data.sandbox import (
    DockerSandbox,
    MountedDataset,
    SandboxUnavailableError,
    docker_available,
)
from agent_data.sandbox.runner import SandboxError
from agent_data.schemas import ExecutionStatus

HAS_DOCKER = docker_available()
_sandbox_ready = HAS_DOCKER and DockerSandbox().image_exists()

needs_docker = pytest.mark.skipif(
    not _sandbox_ready,
    reason="Docker ou l'image du sandbox est indisponible (voir scripts/setup.sh)",
)


# --- garde-fous, testables sans Docker ------------------------------------


def test_refus_d_executer_sans_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sans Docker, on refuse : il ne doit exister aucun repli sur l'hote."""
    monkeypatch.setattr("agent_data.sandbox.runner.docker_available", lambda: False)
    with pytest.raises(SandboxUnavailableError):
        DockerSandbox().run("print('hello')")


def test_argv_confine_le_conteneur(tmp_path: Path) -> None:
    """La ligne de commande doit porter toutes les restrictions attendues."""
    sandbox = DockerSandbox(Settings(_env_file=None))
    argv = sandbox._build_argv(tmp_path, tmp_path / "out", [])
    joined = " ".join(argv)
    assert "--network none" in joined, "le conteneur doit etre coupe du reseau"
    assert "--read-only" in joined
    assert "--cap-drop ALL" in joined
    assert "no-new-privileges" in joined
    assert "--rm" in joined, "le conteneur doit etre jetable"
    assert "--memory" in argv and "--cpus" in argv


def test_datasets_montes_en_lecture_seule(tmp_path: Path) -> None:
    csv = tmp_path / "ventes.csv"
    csv.write_text("a,b\n1,2\n")
    sandbox = DockerSandbox(Settings(_env_file=None))
    argv = sandbox._build_argv(tmp_path, tmp_path / "out", [MountedDataset("ventes", csv)])
    mounts = [argv[i + 1] for i, a in enumerate(argv) if a == "-v"]
    data_mount = next(m for m in mounts if "ventes.csv" in m)
    assert data_mount.endswith(":ro"), "les CSV doivent etre montes en lecture seule"


def test_collecte_ignore_un_artefact_malforme(tmp_path: Path) -> None:
    """Un JSON invalide ne doit pas faire echouer la collecte."""
    (tmp_path / "bad.json").write_text("{pas du json")
    (tmp_path / "ok.json").write_text(
        '{"id":"a1","step_id":"s1","title":"T",'
        '"payload":{"kind":"finding","statement":"ok","evidence":"","confidence":0.5}}'
    )
    artifacts = DockerSandbox._collect_artifacts(tmp_path)
    assert [a.id for a in artifacts] == ["a1"]


def test_build_image_dockerfile_absent(tmp_path: Path) -> None:
    sandbox = DockerSandbox(Settings(_env_file=None))
    if not HAS_DOCKER:
        pytest.skip("Docker indisponible")
    with pytest.raises(SandboxError):
        sandbox.build_image(dockerfile=tmp_path / "absent.Dockerfile")


# --- isolation reelle, necessite Docker -----------------------------------


@needs_docker
def test_execution_simple() -> None:
    result = DockerSandbox().run("print('bonjour')")
    assert result.ok
    assert "bonjour" in result.stdout


@needs_docker
def test_erreur_remontee_sans_lever() -> None:
    result = DockerSandbox().run("raise ValueError('boom')")
    assert result.status is ExecutionStatus.ERROR
    assert "boom" in result.stderr


@needs_docker
def test_boucle_infinie_tuee() -> None:
    sandbox = DockerSandbox(Settings(_env_file=None, sandbox_timeout_seconds=5))
    result = sandbox.run("while True: pass")
    assert result.status is ExecutionStatus.TIMEOUT


@needs_docker
def test_acces_reseau_refuse() -> None:
    code = (
        "import socket\n"
        "try:\n"
        "    socket.create_connection(('1.1.1.1', 53), timeout=5)\n"
        "    print('RESEAU-ACCESSIBLE')\n"
        "except OSError:\n"
        "    print('RESEAU-BLOQUE')\n"
    )
    result = DockerSandbox().run(code)
    assert "RESEAU-BLOQUE" in result.stdout


@needs_docker
def test_lecture_du_csv_monte(tmp_path: Path) -> None:
    csv = tmp_path / "ventes.csv"
    csv.write_text("produit,montant\nclio,100\nclio,150\n")
    code = (
        "import pandas as pd\n"
        "df = pd.read_csv('/workspace/data/ventes.csv')\n"
        "print('TOTAL', int(df['montant'].sum()))\n"
    )
    result = DockerSandbox().run(code, datasets=[MountedDataset("ventes", csv)])
    assert result.ok
    assert "TOTAL 250" in result.stdout


@needs_docker
def test_ecriture_hors_zone_de_sortie_refusee() -> None:
    code = (
        "try:\n"
        "    open('/workspace/interdit.txt', 'w').write('x')\n"
        "    print('ECRITURE-OK')\n"
        "except OSError:\n"
        "    print('ECRITURE-REFUSEE')\n"
    )
    result = DockerSandbox().run(code)
    assert "ECRITURE-REFUSEE" in result.stdout


@needs_docker
def test_artefacts_recuperes_depuis_la_zone_de_sortie() -> None:
    code = (
        "import json\n"
        "art = {'id':'a1','step_id':'s1','title':'Total',"
        "'payload':{'kind':'table','columns':['a'],'rows':[[1]]}}\n"
        "json.dump(art, open('/workspace/out/res.json','w'))\n"
    )
    result = DockerSandbox().run(code)
    assert result.ok
    assert len(result.artifacts) == 1
    assert result.artifacts[0].id == "a1"
