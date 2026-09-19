"""Tests de l'extraction de contenu structure."""

import pytest

from agent_data.llm.parsing import ParseError, extract_json, extract_python


def test_json_nu() -> None:
    assert extract_json('{"a": 1}') == {"a": 1}


def test_json_dans_une_fence() -> None:
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_json_precede_de_bavardage() -> None:
    """Un modele local commente souvent sa reponse : il faut le tolerer."""
    assert extract_json('Voici le plan :\n```json\n{"a": 1}\n```\nBonne analyse !') == {"a": 1}


def test_json_sans_fence_avec_texte_autour() -> None:
    assert extract_json('Reponse: {"a": [1, 2]} voila') == {"a": [1, 2]}


def test_json_invalide() -> None:
    with pytest.raises(ParseError):
        extract_json("desole, je ne peux pas")


def test_python_dans_une_fence() -> None:
    assert extract_python("```python\nprint(1)\n```") == "print(1)"


def test_python_nu() -> None:
    assert extract_python("print(1)") == "print(1)"


def test_python_vide() -> None:
    with pytest.raises(ParseError):
        extract_python("   ")
