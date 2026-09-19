"""Tests de la ligne de commande."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_data.cli import build_parser, main


def test_parser_exige_une_sous_commande() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_ask_exige_un_dataset() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["ask", "question"])


def test_ask_accepte_plusieurs_datasets() -> None:
    args = build_parser().parse_args(["ask", "q", "-d", "a.csv", "-d", "b.csv"])
    assert args.dataset == ["a.csv", "b.csv"]


def test_profile_affiche_le_profil(csv_ventes: Path, capsys: pytest.CaptureFixture) -> None:
    args = build_parser().parse_args(["profile", str(csv_ventes)])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "ventes" in out
    assert "montant" in out


def test_ask_sur_csv_absent(capsys: pytest.CaptureFixture) -> None:
    args = build_parser().parse_args(["ask", "q", "-d", "/introuvable.csv"])
    assert args.func(args) == 1
    assert "introuvable" in capsys.readouterr().err.lower()


def test_main_propage_le_code_de_sortie(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["agent-data", "ask", "q", "-d", "/nope.csv"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
