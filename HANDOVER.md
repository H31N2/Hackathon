# Übergabe – Stand 20.11.2026

## Was fertig ist
- Erkennung (Regeln, optional spaCy-NER), Zuordnung von Schreibvarianten (Normalisierung +
  EmbeddingGemma über Ollama oder sentence-transformers), verschlüsselter Tresor, positionsgenaue
  Anonymisierung, tolerante Rückanonymisierung, Harness-Prüfungen vor/nach Claude.
- Eingabe DOCX (inkl. Tabellen, Kopf-/Fußzeilen, über mehrere Läufe verteilte Namen), PDF (nur Text-PDF),
  TXT/MD. Ausgabe Ergebnis als DOCX; anonyme DOCX formatgetreu mit XML-Leck-Scan.
- Kommandozeile und lokale Weboberfläche mit Prüfansicht; Starter `Vertrags-Anonymisierer.bat`.
- 25 Tests grün (fiktiver Korpus, Claude-Attrappe, Web-API).

## Noch nicht geprüft
- **Echter Claude-API-Aufruf**: in der Entwicklungsumgebung gab es keinen API-Schlüssel; der Aufruf ist nur
  gegen die Attrappe getestet. Erster Live-Test mit `tests/korpus/kaufvertrag.txt`.
- **EmbeddingGemma live**: Schnittstellen (Ollama `/api/embed`, sentence-transformers) sind gebaut, aber
  nur mit Test-Vektoren geprüft. Schwelle 0.9 an echten Daten nachjustieren.
- spaCy-NER nicht installiert getestet.

## Bekannte Grenzen / nächste Schritte
- Namen ohne Anrede und ohne bekannten Vornamen findet nur NER oder der Mensch (Prüfansicht).
- Orte werden überall ersetzt, auch „Amtsgericht Köln“; abschaltbar mit `typen_aus = ["ORT"]`.
- Gescannte PDFs werden abgelehnt (OCR fehlt).
- Ergebnis-DOCX ist schlicht formatiert (Überschriften, fett, Aufzählungen); Briefkopf-Vorlage wäre ein
  sinnvoller nächster Schritt.
- Tresor-Schlüssel liegt als Datei neben der Datenbank; für mehr Schutz Windows-DPAPI erwägen.
