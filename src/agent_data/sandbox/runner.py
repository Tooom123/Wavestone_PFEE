"""Execution isolee du code genere par le LLM.

Le code produit par un LLM n'est jamais execute sur l'hote : il tourne dans un conteneur
Docker **sans reseau**, en utilisateur non privilegie, avec un systeme de fichiers en
lecture seule hormis une zone de sortie, sous quota memoire/CPU et sous timeout.

Regle de conception : en cas de doute, on **refuse d'executer**. Si Docker est absent,
:class:`DockerSandbox` leve :class:`SandboxUnavailableError` — il n'existe deliberement
aucun repli qui executerait le code sur la machine hote.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from agent_data.config import Settings, get_settings
from agent_data.schemas import Artifact, ExecutionResult, ExecutionStatus


class SandboxError(RuntimeError):
    """Erreur liee au sandbox."""


class SandboxUnavailableError(SandboxError):
    """Docker est introuvable ou hors service : aucune execution n'est possible."""


@dataclass(frozen=True)
class MountedDataset:
    """Un CSV monte en lecture seule dans le conteneur."""

    name: str
    host_path: Path

    @property
    def container_path(self) -> str:
        return f"/workspace/data/{self.host_path.name}"


def docker_available() -> bool:
    """Vrai si un daemon Docker repond."""
    binary = shutil.which("docker")
    if binary is None:
        return False
    try:
        done = subprocess.run(  # noqa: S603
            [binary, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


class DockerSandbox:
    """Execute du code Python dans un conteneur jetable et confine."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    # -- construction de l'image ------------------------------------------
    def image_exists(self) -> bool:
        binary = shutil.which("docker")
        if binary is None:
            return False
        done = subprocess.run(  # noqa: S603
            [binary, "image", "inspect", self.settings.sandbox_image],
            capture_output=True,
            timeout=30,
            check=False,
        )
        return done.returncode == 0

    def build_image(self, dockerfile: Path | None = None) -> None:
        """Construit l'image du sandbox."""
        self._require_docker()
        path = dockerfile or Path(__file__).resolve().parents[3] / "docker" / "sandbox.Dockerfile"
        if not path.exists():
            raise SandboxError(f"Dockerfile introuvable : {path}")
        done = subprocess.run(  # noqa: S603
            [
                "docker",
                "build",
                "-t",
                self.settings.sandbox_image,
                "-f",
                str(path),
                str(path.parent),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if done.returncode != 0:
            raise SandboxError(f"Echec du build de l'image : {done.stderr[-2000:]}")

    # -- execution ---------------------------------------------------------
    def run(self, code: str, datasets: list[MountedDataset] | None = None) -> ExecutionResult:
        """Execute `code` dans le conteneur et retourne le resultat."""
        self._require_docker()
        datasets = datasets or []

        with tempfile.TemporaryDirectory(prefix="agent-data-") as tmp:
            workdir = Path(tmp)
            (workdir / "code.py").write_text(code, encoding="utf-8")
            out_dir = workdir / "out"
            out_dir.mkdir()
            # Le conteneur ecrit en tant qu'uid 10001 : la zone de sortie doit lui etre ouverte.
            out_dir.chmod(0o777)

            argv = self._build_argv(workdir, out_dir, datasets)
            started = time.monotonic()
            try:
                done = subprocess.run(  # noqa: S603
                    argv,
                    capture_output=True,
                    text=True,
                    timeout=self.settings.sandbox_timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                # Le conteneur peut survivre au timeout cote client : on le tue explicitement.
                self._force_remove(argv)
                return ExecutionResult(
                    status=ExecutionStatus.TIMEOUT,
                    stderr=(
                        f"Execution interrompue apres "
                        f"{self.settings.sandbox_timeout_seconds}s (timeout)."
                    ),
                    duration_seconds=float(self.settings.sandbox_timeout_seconds),
                )

            duration = time.monotonic() - started
            artifacts = self._collect_artifacts(out_dir)
            status = ExecutionStatus.SUCCESS if done.returncode == 0 else ExecutionStatus.ERROR
            return ExecutionResult(
                status=status,
                stdout=done.stdout[-20_000:],
                stderr=done.stderr[-20_000:],
                artifacts=artifacts,
                duration_seconds=duration,
            )

    # -- interne -----------------------------------------------------------
    def _require_docker(self) -> None:
        if not docker_available():
            raise SandboxUnavailableError(
                "Docker est indisponible. Le code genere ne peut pas etre execute : il n'y a "
                "aucun repli sur la machine hote, par conception. Demarrer Docker (sous WSL, "
                "activer l'integration dans Docker Desktop) puis relancer."
            )

    def _build_argv(
        self, workdir: Path, out_dir: Path, datasets: list[MountedDataset]
    ) -> list[str]:
        name = f"agent-data-{uuid.uuid4().hex[:12]}"
        argv = [
            "docker",
            "run",
            "--rm",
            "--name",
            name,
            "--network",
            "none",  # aucun acces reseau
            "--read-only",  # racine en lecture seule
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "256",
            "--memory",
            self.settings.sandbox_memory_limit,
            "--cpus",
            str(self.settings.sandbox_cpus),
            # /tmp en tmpfs : pandas a besoin d'ecrire quelque part, sans persistance.
            "--tmpfs",
            "/tmp:rw,size=256m,noexec",  # nosec B108 - chemin dans le conteneur, pas sur l'hote
            "-v",
            f"{workdir / 'code.py'}:/workspace/code.py:ro",
            "-v",
            f"{out_dir}:/workspace/out:rw",
        ]
        for dataset in datasets:
            argv += ["-v", f"{dataset.host_path.resolve()}:{dataset.container_path}:ro"]
        argv.append(self.settings.sandbox_image)
        return argv

    @staticmethod
    def _force_remove(argv: list[str]) -> None:
        """Supprime le conteneur si le timeout client l'a laisse vivant."""
        try:
            name = argv[argv.index("--name") + 1]
        except (ValueError, IndexError):
            return
        subprocess.run(  # noqa: S603
            ["docker", "rm", "-f", name], capture_output=True, timeout=30, check=False
        )

    @staticmethod
    def _collect_artifacts(out_dir: Path) -> list[Artifact]:
        """Lit les artefacts JSON deposes par le code dans la zone de sortie."""
        artifacts: list[Artifact] = []
        for path in sorted(out_dir.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            items = raw if isinstance(raw, list) else [raw]
            for item in items:
                try:
                    artifacts.append(Artifact.model_validate(item))
                except ValueError:
                    # Un artefact malforme ne doit pas faire echouer tout le run :
                    # le critique verra qu'il manque un resultat.
                    continue
        return artifacts
