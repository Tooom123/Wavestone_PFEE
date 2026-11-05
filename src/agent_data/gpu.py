"""Mesures du GPU : caracteristiques, et consommation d'un run.

Ces mesures servent deux choses : montrer sur quel materiel tourne l'agent (bloc GPU de la
demo) et chiffrer ce qu'un run coute en energie, donnee de base du benchmark on-premise
contre cloud. Sans GPU NVIDIA (ou sans `nvidia-smi`), tout se degrade en valeurs absentes :
la mesure ne doit jamais faire echouer un run.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

_QUERY = "name,memory.total,memory.used,power.draw,power.limit,utilization.gpu,driver_version"


@dataclass
class GpuInfo:
    """Caracteristiques du GPU, telles que rapportees par le pilote."""

    name: str
    memory_total_mb: int
    power_limit_w: float
    driver: str

    def as_dict(self) -> dict[str, str | int | float]:
        return {
            "name": self.name,
            "memory_total_mb": self.memory_total_mb,
            "power_limit_w": self.power_limit_w,
            "driver": self.driver,
        }


@dataclass
class Sample:
    """Un releve instantane."""

    memory_used_mb: float
    power_w: float
    utilization_pct: float


def _num(text: str) -> float:
    try:
        return float(text.strip().split()[0])
    except (ValueError, IndexError):
        return 0.0


def _read_line() -> list[str] | None:
    binary = shutil.which("nvidia-smi")
    if binary is None:
        return None
    try:
        done = subprocess.run(  # noqa: S603
            [binary, f"--query-gpu={_QUERY}", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0 or not done.stdout.strip():
        return None
    return [part.strip() for part in done.stdout.splitlines()[0].split(",")]


def gpu_info() -> GpuInfo | None:
    """Caracteristiques du premier GPU, ou None sans NVIDIA."""
    parts = _read_line()
    if parts is None or len(parts) < 7:
        return None
    return GpuInfo(
        name=parts[0],
        memory_total_mb=int(_num(parts[1])),
        power_limit_w=_num(parts[4]),
        driver=parts[6],
    )


def read_sample() -> Sample | None:
    parts = _read_line()
    if parts is None or len(parts) < 7:
        return None
    return Sample(
        memory_used_mb=_num(parts[2]), power_w=_num(parts[3]), utilization_pct=_num(parts[5])
    )


@dataclass
class GpuMetrics:
    """Consommation du GPU sur la duree d'un run."""

    seconds: float = 0.0
    energy_wh: float = 0.0
    avg_power_w: float = 0.0
    peak_power_w: float = 0.0
    peak_memory_mb: float = 0.0
    avg_utilization_pct: float = 0.0
    samples: int = 0

    def as_dict(self) -> dict[str, float | int]:
        return {
            "seconds": round(self.seconds, 1),
            "energy_wh": round(self.energy_wh, 2),
            "avg_power_w": round(self.avg_power_w, 1),
            "peak_power_w": round(self.peak_power_w, 1),
            "peak_memory_mb": round(self.peak_memory_mb),
            "avg_utilization_pct": round(self.avg_utilization_pct, 1),
            "samples": self.samples,
        }


@dataclass
class GpuSampler:
    """Echantillonne le GPU en tache de fond et integre la puissance en energie (Wh).

    `reader` et `clock` sont injectables pour tester sans GPU.
    """

    interval: float = 1.0
    reader: Callable[[], Sample | None] = read_sample
    clock: Callable[[], float] = time.monotonic
    _points: list[tuple[float, Sample]] = field(default_factory=list, init=False)
    _stop: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)

    def start(self) -> None:
        self._stop.clear()
        self._record()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _record(self) -> None:
        sample = self.reader()
        if sample is not None:
            self._points.append((self.clock(), sample))

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            self._record()

    def stop(self) -> GpuMetrics:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval + 6)
        self._record()
        return self.metrics()

    def metrics(self) -> GpuMetrics:
        points = self._points
        if len(points) < 2:
            return GpuMetrics(samples=len(points))
        energy_ws = 0.0
        for (t0, a), (t1, b) in zip(points, points[1:], strict=False):
            energy_ws += (a.power_w + b.power_w) / 2 * (t1 - t0)  # trapeze
        seconds = points[-1][0] - points[0][0]
        samples = [p for _, p in points]
        return GpuMetrics(
            seconds=seconds,
            energy_wh=energy_ws / 3600,
            avg_power_w=energy_ws / seconds if seconds else 0.0,
            peak_power_w=max(s.power_w for s in samples),
            peak_memory_mb=max(s.memory_used_mb for s in samples),
            avg_utilization_pct=sum(s.utilization_pct for s in samples) / len(samples),
            samples=len(samples),
        )
