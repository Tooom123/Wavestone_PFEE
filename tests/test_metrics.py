"""Mesures d'un run : tokens par agent et energie du GPU."""

from __future__ import annotations

import io
import json
from typing import Any

import pytest

from agent_data.config import Settings
from agent_data.gpu import GpuSampler, Sample
from agent_data.llm import OllamaClient, Usage


class _Response(io.BytesIO):
    status = 200

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *exc: Any) -> None:
        return None


def test_ollama_compte_les_tokens_et_les_durees(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "response": " bonjour ",
        "prompt_eval_count": 120,
        "eval_count": 30,
        "total_duration": 2_500_000_000,
        "load_duration": 400_000_000,
    }
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **k: _Response(json.dumps(payload).encode())
    )
    client = OllamaClient(Settings(_env_file=None), model="m")

    assert client.complete("salut") == "bonjour"
    client.complete("encore")

    assert client.usage.calls == 2
    assert client.usage.prompt_tokens == 240
    assert client.usage.completion_tokens == 60
    assert client.usage.seconds == pytest.approx(5.0)
    assert client.usage.load_seconds == pytest.approx(0.8)


def test_usage_s_additionne() -> None:
    total = Usage(calls=1, prompt_tokens=10)
    total.add(Usage(calls=2, prompt_tokens=5, completion_tokens=7))
    assert (total.calls, total.prompt_tokens, total.completion_tokens) == (3, 15, 7)


def test_energie_integree_par_la_methode_des_trapezes() -> None:
    # 100 W pendant 10 s puis 200 W : trapeze = (100+200)/2 * 10 = 1500 Ws
    releves = iter([Sample(1000, 100, 10), Sample(1500, 200, 90)])
    horloge = iter([0.0, 10.0])
    sampler = GpuSampler(interval=999, reader=lambda: next(releves), clock=lambda: next(horloge))
    sampler._record()
    sampler._record()

    m = sampler.metrics()

    assert m.energy_wh == pytest.approx(1500 / 3600)
    assert m.avg_power_w == pytest.approx(150)
    assert m.peak_power_w == 200
    assert m.peak_memory_mb == 1500
    assert m.seconds == 10


def test_sans_gpu_la_mesure_se_degrade_sans_echouer() -> None:
    sampler = GpuSampler(interval=0.01, reader=lambda: None)
    sampler.start()
    m = sampler.stop()
    assert m.samples == 0 and m.energy_wh == 0
