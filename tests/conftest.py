import re
from pathlib import Path
from types import SimpleNamespace

import pytest

KORPUS = Path(__file__).parent / "korpus"


@pytest.fixture(autouse=True)
def datenordner(tmp_path, monkeypatch):
    monkeypatch.setenv("VERTRAGS_ANONYMISIERER_DATEN", str(tmp_path / "daten"))
    monkeypatch.delenv("VERTRAGS_ANONYMISIERER_SCHLUESSEL", raising=False)
    return tmp_path / "daten"


@pytest.fixture
def korpus():
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(KORPUS.glob("*.txt"))}


class _Stream:
    def __init__(self, antwort):
        self.antwort = antwort

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return SimpleNamespace(
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=self.antwort)],
            stop_reason="end_turn", model="claude-opus-5-5",
            usage=SimpleNamespace(input_tokens=100, output_tokens=50),
        )


class FalscherClaude:
    """Ersetzt die API: gibt das Dokument zurück, verstümmelt dabei Platzhalter wie ein Sprachmodell es könnte."""

    def __init__(self, umbau=None):
        self.anfragen = []
        self.umbau = umbau or (lambda t: re.sub(r"\[NACHNAME_(\d+)\]", r"[Nachname \1]", t))
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kw):
        self.anfragen.append(kw)
        inhalt = kw["messages"][0]["content"]
        dok = re.search(r"<dokument>\n(.*)\n</dokument>", inhalt, re.S)
        return _Stream("# Überarbeitung\n\n" + self.umbau(dok.group(1) if dok else inhalt))


@pytest.fixture
def falscher_claude():
    return FalscherClaude()
