"""Übergabe des anonymisierten Texts an die Claude API.

An Claude geht ausschließlich: Systemanweisung, anonymisierter Auftrag und
anonymisiertes Dokument. Der Tresor bleibt lokal.
"""

from __future__ import annotations

from dataclasses import dataclass

SYSTEM = """Du arbeitest für ein deutsches Notariat und bearbeitest oder erstellst Verträge und Unterlagen.

Alle personenbezogenen Daten sind durch Platzhalter in eckigen Klammern ersetzt, z. B. [VORNAME_1], [NACHNAME_1], [NACHNAME_1_B], [STRASSE_2], [GEBURTSDATUM_1], [FIRMA_1], [IBAN_1].
Gleiche Nummer = dieselbe Person bzw. Sache. Ein Buchstabe am Ende (_B, _C) ist nur eine andere Schreibweise desselben Werts.

Regeln für Platzhalter (zwingend):
1. Übernimm jeden Platzhalter Zeichen für Zeichen unverändert, inklusive eckiger Klammern, Großschreibung und Unterstrich.
2. Erfinde keine neuen Platzhalter und keine echten Namen, Anschriften oder Nummern. Fehlt eine Angabe, schreibe stattdessen "[OFFEN: kurze Beschreibung]".
3. Löse Platzhalter nie auf, rate keine Werte und kommentiere nicht, dass Daten anonymisiert sind.
4. Grammatik um den Platzhalter herum ist erlaubt (z. B. Genitiv: "[NACHNAME_1]s Anteil").

Antworte auf Deutsch. Gib das Ergebnisdokument als reinen Text mit einfacher Markdown-Gliederung aus (# Überschriften, **fett**, - Aufzählungen). Hinweise an den Bearbeiter setze ans Ende unter "## Hinweise"."""


@dataclass
class Antwort:
    text: str
    modell: str
    stop_reason: str | None
    eingabe_tokens: int
    ausgabe_tokens: int


class ClaudeFehler(RuntimeError):
    pass


def nachricht_bauen(auftrag_anonym: str, dokument_anonym: str | None) -> str:
    teile = [f"<auftrag>\n{auftrag_anonym}\n</auftrag>"]
    if dokument_anonym:
        teile.insert(0, f"<dokument>\n{dokument_anonym}\n</dokument>")
    return "\n\n".join(teile)


def senden(auftrag_anonym: str, dokument_anonym: str | None, *, modell: str = "claude-opus-5-5",
           effort: str = "high", max_tokens: int = 64000, client=None) -> Antwort:
    """Ein Aufruf, gestreamt (lange Verträge), mit serverseitigem Ausweichmodell bei Ablehnung."""
    import anthropic

    client = client or anthropic.Anthropic()
    try:
        with client.beta.messages.stream(
            model=modell,
            max_tokens=max_tokens,
            system=SYSTEM,
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": nachricht_bauen(auftrag_anonym, dokument_anonym)}],
        ) as stream:
            nachricht = stream.get_final_message()
    except anthropic.AuthenticationError as fehler:
        raise ClaudeFehler("Claude API: Schlüssel fehlt oder ist ungültig (ANTHROPIC_API_KEY).") from fehler
    except anthropic.RateLimitError as fehler:
        raise ClaudeFehler("Claude API: Anfragelimit erreicht – bitte später erneut versuchen.") from fehler
    except anthropic.APIStatusError as fehler:
        raise ClaudeFehler(f"Claude API: Fehler {fehler.status_code}: {fehler.message}") from fehler
    except anthropic.APIConnectionError as fehler:
        raise ClaudeFehler("Claude API nicht erreichbar (Netzwerk/Proxy prüfen).") from fehler

    if nachricht.stop_reason == "refusal":
        raise ClaudeFehler("Claude hat den Auftrag abgelehnt.")
    text = "".join(b.text for b in nachricht.content if b.type == "text")
    if nachricht.stop_reason == "max_tokens":
        raise ClaudeFehler("Antwort wurde wegen der Längenbegrenzung abgeschnitten (max_tokens erhöhen).")
    return Antwort(text, nachricht.model, nachricht.stop_reason, nachricht.usage.input_tokens, nachricht.usage.output_tokens)
