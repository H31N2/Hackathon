"""Tresor: Zuordnung Platzhalter -> Originalwert, je Vorgang verschlüsselt.

Liegt nur auf dem Arbeitsplatz (SQLite unter LOCALAPPDATA). Die Originalwerte
verlassen den Rechner nie; an Claude geht nur der anonymisierte Text.
Der Schlüssel liegt in einer eigenen Datei neben der Datenbank oder kommt aus
der Umgebungsvariable VERTRAGS_ANONYMISIERER_SCHLUESSEL.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


def datenordner() -> Path:
    basis = os.environ.get("VERTRAGS_ANONYMISIERER_DATEN")
    if basis:
        p = Path(basis)
    elif os.name == "nt":
        p = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "VertragsAnonymisierer"
    else:
        p = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "vertrags-anonymisierer"
    p.mkdir(parents=True, exist_ok=True)
    return p


class Tresor:
    def __init__(self, ordner: Path | None = None):
        self.ordner = ordner or datenordner()
        self.ordner.mkdir(parents=True, exist_ok=True)
        self._fernet = Fernet(self._schluessel())
        self._db = sqlite3.connect(self.ordner / "tresor.db")
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS vorgang (
                   id TEXT PRIMARY KEY,
                   angelegt TEXT NOT NULL,
                   bezeichnung TEXT NOT NULL,
                   zuordnung BLOB NOT NULL,
                   anonym_text TEXT,
                   antwort_text TEXT
               )"""
        )
        self._db.commit()

    def _schluessel(self) -> bytes:
        aus_umgebung = os.environ.get("VERTRAGS_ANONYMISIERER_SCHLUESSEL")
        if aus_umgebung:
            return aus_umgebung.encode()
        datei = self.ordner / "tresor.key"
        if not datei.exists():
            datei.write_bytes(Fernet.generate_key())
            try:
                os.chmod(datei, 0o600)
            except OSError:
                pass
        return datei.read_bytes().strip()

    def speichern(self, zuordnung: dict[str, str], bezeichnung: str, anonym_text: str = "") -> str:
        vid = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        geheim = self._fernet.encrypt(json.dumps(zuordnung, ensure_ascii=False).encode())
        self._db.execute(
            "INSERT INTO vorgang (id, angelegt, bezeichnung, zuordnung, anonym_text) VALUES (?,?,?,?,?)",
            (vid, datetime.now().isoformat(timespec="seconds"), bezeichnung, geheim, anonym_text),
        )
        self._db.commit()
        return vid

    def antwort_speichern(self, vid: str, antwort_text: str) -> None:
        self._db.execute("UPDATE vorgang SET antwort_text=? WHERE id=?", (antwort_text, vid))
        self._db.commit()

    def laden(self, vid: str) -> dict[str, str]:
        zeile = self._db.execute("SELECT zuordnung FROM vorgang WHERE id=?", (vid,)).fetchone()
        if zeile is None:
            raise KeyError(f"Vorgang {vid} nicht gefunden")
        try:
            return json.loads(self._fernet.decrypt(zeile[0]))
        except InvalidToken as fehler:
            raise RuntimeError("Tresor-Schlüssel passt nicht zu diesem Vorgang.") from fehler

    def vorgaenge(self) -> list[tuple[str, str, str]]:
        return self._db.execute("SELECT id, angelegt, bezeichnung FROM vorgang ORDER BY angelegt DESC").fetchall()

    def schliessen(self) -> None:
        self._db.close()
