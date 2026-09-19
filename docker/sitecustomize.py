"""Adaptations appliquees automatiquement dans le sandbox.

`sitecustomize` est importe par Python au demarrage : le code genere en beneficie sans
avoir a le demander.

Le LLM produit regulierement des valeurs numpy (`int64`, `float64`, `ndarray`) et les
passe telles quelles a `json.dump`, qui les refuse. Plutot que de compter sur le prompt
pour l'eviter a tous les coups, on rend l'encodeur JSON tolerant a ces types.
"""

from __future__ import annotations

import datetime as _dt
import json as _json

try:
    import numpy as _np
except ImportError:  # pragma: no cover
    _np = None  # type: ignore[assignment]

_default = _json.JSONEncoder.default


def _encode(self, obj):  # type: ignore[no-untyped-def]
    if _np is not None:
        if isinstance(obj, _np.integer):
            return int(obj)
        if isinstance(obj, _np.floating):
            return float(obj)
        if isinstance(obj, _np.bool_):
            return bool(obj)
        if isinstance(obj, _np.ndarray):
            return obj.tolist()
    if isinstance(obj, (_dt.datetime, _dt.date)):
        return obj.isoformat()
    if hasattr(obj, "item"):  # scalaires numpy/pandas restants
        try:
            return obj.item()
        except (ValueError, AttributeError):
            pass
    if hasattr(obj, "to_dict"):  # Series / DataFrame
        return obj.to_dict()
    return _default(self, obj)


_json.JSONEncoder.default = _encode  # type: ignore[method-assign]
