# Vertrags-Anonymisierer

Verträge und Unterlagen werden **auf dem Arbeitsplatz** anonymisiert, an **Claude** zur Bearbeitung
(oder zum Erstellen eines Vertrags) übergeben und danach **fehlerfrei zurückanonymisiert**.

```
 Original.docx ──► Erkennung ──► Prüfansicht ──► Platzhalter ──► Harness ──► Claude API
 (lokal)          Regeln+NER      (Mensch)       [VORNAME_1]     grün?        (nur anonym)
                  EmbeddingGemma                 [NACHNAME_1]                      │
                                                     │                             ▼
 Ergebnis.docx ◄── Rückanonymisierung ◄── Harness ◄──┴── Tresor (verschlüsselt, lokal)
```

- **Platzhalter**: `[VORNAME_1]`, `[NACHNAME_1]`, `[STRASSE_1]`, `[GEBURTSDATUM_1]`, `[IBAN_1]` … Gleiche
  Nummer = dieselbe Person/Sache. Andere Schreibweisen desselben Werts (z. B. `MÜLLER` in der
  Unterschriftszeile) erhalten einen Buchstaben: `[NACHNAME_1_B]`. Liste: `vertrags-anonymisierer typen`.
- **Fehlerfreier Rückweg**: Jeder Platzhalter steht für genau eine exakte Schreibweise, ersetzt wird
  positionsgenau. Vor jedem Versand prüft der Harness, dass die Rückanonymisierung **bytegleich** das
  Original ergibt – sonst wird nichts gesendet.
- **Tresor**: Die Zuordnung Platzhalter → Original liegt verschlüsselt (Fernet) in
  `%LOCALAPPDATA%\VertragsAnonymisierer\tresor.db`. Sie verlässt den Rechner nie.

## Einrichtung (Windows)

```bat
cd hackathon
python -m venv .venv
.venv\Scripts\pip install -e .
copy config.example.toml config.toml
setx ANTHROPIC_API_KEY "sk-ant-..."
```

EmbeddingGemma (empfohlen, ordnet Schreibvarianten zu):

- **Ollama** (einfachste Variante): Ollama installieren, dann `ollama pull embeddinggemma`;
  in `config.toml` `backend = "ollama"`.
- **ohne Ollama**: `.venv\Scripts\pip install -e .[embedding]`, `backend = "sentence-transformers"`,
  `modell = "google/embeddinggemma-300m"` (Lizenz auf Hugging Face einmal bestätigen).
- Läuft keines von beiden, arbeitet das Tool mit reiner Normalisierung weiter (Meldung im Log).

Zusätzliche Namenserkennung ohne Anrede (optional): `pip install -e .[ner]`,
`python -m spacy download de_core_news_lg`, in `config.toml` `ner_modell = "de_core_news_lg"`.

## Bedienung

**Weboberfläche** – Doppelklick auf `Vertrags-Anonymisierer.bat` (öffnet `http://127.0.0.1:8765`):

1. Dokument wählen (oder leer lassen für „Vertrag erstellen“), Auftrag eingeben.
2. **Prüfansicht**: erkannte Werte, Platzhalter und „So sieht Claude den Text“. Übersehenes ergänzen,
   Falsches abhaken. Erst bei grüner Prüfung und Bestätigung ist „An Claude senden“ möglich.
3. Ergebnis mit Prüfbericht ansehen und als Word-Datei herunterladen.

Ohne API-Schlüssel: anonymen Text aus der Prüfansicht in claude.ai einfügen und die Antwort unter
„Ohne API“ wieder einfügen.

**Kommandozeile**

```bat
vertrags-anonymisierer pruefen Vertrag.docx --anzeigen            :: nur anonymisieren, nichts senden
vertrags-anonymisierer pruefen Vertrag.docx --docx anonym.docx    :: anonyme DOCX mit Formatierung
vertrags-anonymisierer bearbeiten Vertrag.docx -a "Prüfe § 5 und formuliere ihn neu"
vertrags-anonymisierer bearbeiten -a "Entwirf eine Vorsorgevollmacht für Herrn Max Beispiel, geb. 01.01.1950"
vertrags-anonymisierer bearbeiten Vertrag.pdf -a "…" -e NACHNAME=Weißenburger --ohne ORT=Köln
vertrags-anonymisierer zurueck 20261120-101500-ab12cd Antwort.txt  :: Antwort nachträglich zurückführen
vertrags-anonymisierer vorgaenge
```

Rückgabewert 0 = grün, 1 = Prüfung rot, 2 = Claude-Fehler.

## Was erkannt wird

Namen nach Anrede (Herr/Frau/Notar, auch mit Titel und „von der“), „Eheleute A und B Name“, häufige
Vornamen + Nachname, Geburtsnamen (geb.), Geburtsdaten, Straße + Hausnummer, PLZ + Ort, IBAN (mit
Prüfziffer), BIC, E-Mail, Telefon, Steuer-ID, Ausweisnummer, UR-/UVZ-Nr., Grundbuchbezirk/Gemarkung,
Blatt, Flurstück, Firmen mit Rechtsform; optional Geldbeträge. Namen werden anschließend **überall** im
Text gesucht (auch GROSS, ae/ä, Genitiv „Müllers“). Was die Regeln nicht kennen, ergänzt der Mensch in
der Prüfansicht – deshalb ist die Prüfansicht Pflicht.

## Harness-Prüfungen

| Wann | Prüfung | Folge |
|---|---|---|
| vor Versand | Round-Trip bytegleich | rot → Versand gesperrt |
| vor Versand | Leck-Scan (alle Originalwerte, auch GROSS/ae/ohne Leerzeichen) | rot → gesperrt |
| vor Versand | Nacherkennung über den anonymen Text | Warnung |
| nach Antwort | Platzhalter-Abgleich, tolerant (`[Vorname 1]` → `[VORNAME_1]`) | Info |
| nach Antwort | unbekannte/erfundene Platzhalter | rot, bleiben sichtbar stehen |
| nach Antwort | neue Namen/IBAN/E-Mail, die Claude selbst einführt | Warnung |
| anonyme DOCX | Leck-Scan über das gesamte Word-XML (Kopf/Fuß, Kommentare, Änderungen, Metadaten) | rot |

## Tests

```bat
.venv\Scripts\pip install -e .[dev]
.venv\Scripts\python -m pytest
```

Die Tests nutzen nur **fiktive** Musterverträge (`tests/korpus/`) und eine Claude-Attrappe.
