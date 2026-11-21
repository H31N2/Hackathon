# Regeln für Claude Code in diesem Repository

Projekt: Vertrags-Anonymisierer (Python ≥ 3.11, Paket `src/vertrags_anonymisierer`). Doku auf Deutsch,
Code-Bezeichner auf Deutsch (bestehenden Stil beibehalten).

## Unverhandelbar (Harness)
- Das Kernversprechen ist `einsetzen(anonymisiere(text)) == text` (bytegleich). Jede Änderung an
  Erkennung, Platzhaltern oder Ersetzung muss `tests/test_rundweg.py` grün lassen.
- Niemals echte Personendaten in Code, Tests, Commits oder Logs. Testdaten nur fiktiv in `tests/korpus/`.
- Das Protokoll (`protokoll.jsonl`) enthält nur IDs, Zahlen und Prüfergebnisse – keine Werte.
- An die Claude API geht ausschließlich der anonymisierte Text (`vorgang.Vorgang.an_claude`).
  Kein zweiter Weg an `harness.pruefung.vor_versand` vorbei.
- Unbekannte Platzhalter in Antworten werden nie geraten, sondern stehen gelassen und rot gemeldet.

## Arbeitsweise
- Neue Erkennungsregel → Fall in `tests/korpus/` ergänzen + Erwartung in `tests/test_rundweg.py`.
- Muster in `erkennung/regeln.py` dürfen keine Zeilenumbrüche überspannen (`S`/`SZ` statt `\s`).
- Positionsgebundene Typen (PLZ, Blatt, Flurstück …) nicht in `WERT_TYPEN` aufnehmen, sonst werden
  gleiche Zahlen an anderer Stelle (z. B. „§ 12“) mit ersetzt.
- Tests: `python -m pytest`. Claude-Aufrufe in Tests nur über `tests/conftest.py::FalscherClaude`.
- Modell-Standard: `claude-opus-5-5` (config.toml), Aufruf gestreamt mit adaptivem Denken und
  serverseitigem Ausweichmodell.
