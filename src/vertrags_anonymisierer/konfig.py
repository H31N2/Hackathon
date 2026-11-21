"""Konfiguration (TOML). Pfad: --konfig, VERTRAGS_ANONYMISIERER_CONFIG oder config.toml im Projektordner."""

from __future__ import annotations

import copy
import os
import tomllib
from pathlib import Path

STANDARD = {
    "claude": {"modell": "claude-opus-5-5", "effort": "high", "max_tokens": 64000},
    "erkennung": {"betraege": False, "ner_modell": "", "typen_aus": []},
    "embedding": {"backend": "aus", "modell": "", "url": "http://127.0.0.1:11434", "schwelle": 0.9},
    "ablage": {"ausgabe": "ausgabe"},
}


def _mischen(basis: dict, neu: dict) -> dict:
    for k, v in neu.items():
        if isinstance(v, dict) and isinstance(basis.get(k), dict):
            _mischen(basis[k], v)
        else:
            basis[k] = v
    return basis


def laden(pfad: str | Path | None = None) -> dict:
    konfig = copy.deepcopy(STANDARD)
    kandidat = pfad or os.environ.get("VERTRAGS_ANONYMISIERER_CONFIG") or "config.toml"
    p = Path(kandidat)
    if p.exists():
        with p.open("rb") as f:
            _mischen(konfig, tomllib.load(f))
    elif pfad:
        raise FileNotFoundError(f"Konfiguration {p} nicht gefunden")
    return konfig
