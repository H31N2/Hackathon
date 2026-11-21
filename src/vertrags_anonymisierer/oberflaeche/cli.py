"""Kommandozeile: vertrags-anonymisierer <befehl>."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from .. import konfig as konfig_mod
from ..claude.auftrag import ClaudeFehler
from ..einlesen.dokument import text_laden
from ..harness import pruefung
from ..platzhalter.tresor import Tresor
from ..rueck.ausgabe import speichern
from ..typen import TYPEN, Pruefbericht
from ..vorgang import Vorgang

app = typer.Typer(add_completion=False, help="Verträge anonymisieren, mit Claude bearbeiten, fehlerfrei zurückführen.")
KONFIG = typer.Option(None, "--konfig", help="Pfad zur config.toml")


def _bericht(titel: str, b: Pruefbericht) -> None:
    farbe = typer.colors.GREEN if b.gruen else typer.colors.RED
    typer.secho(f"\n== {titel}: {'GRÜN' if b.gruen else 'ROT'} ==", fg=farbe, bold=True)
    for m in b.meldungen:
        typer.echo(f"  {m}")


def _vorbereiten(datei: Optional[Path], auftrag: str, ergaenze: list[str], ohne: list[str], konfig: Optional[Path]) -> Vorgang:
    v = Vorgang(konfig_mod.laden(konfig))
    v.laden(datei, auftrag)
    for e in ergaenze:
        typ, _, wert = e.partition("=")
        v.ergaenze(typ, wert)
    for o in ohne:
        typ, _, wert = o.partition("=")
        v.anonymisierer.setze_aktiv(typ.upper(), wert, False)
    v.vorbereiten()
    typer.secho("\nErkannte Daten (Platzhalter ← Original):", bold=True)
    for ph, e in v.anonymisierer.zuordnung.items():
        k = v.anonymisierer.kandidaten.get((e.typ, e.wert))
        hinweis = "" if (k and k.sicher) else "   (unsicher)"
        typer.echo(f"  {ph:22} ← {e.wert}{hinweis}")
    aus = [k for k in v.anonymisierer.kandidaten.values() if not k.aktiv]
    for k in aus:
        typer.echo(f"  {'(ausgenommen)':22}   {k.wert} [{k.typ}]")
    _bericht("Prüfung vor Versand", v.bericht_vorher)
    return v


@app.command()
def pruefen(
    datei: Optional[Path] = typer.Argument(None, exists=True, help="DOCX, PDF oder TXT"),
    auftrag: str = typer.Option("", "--auftrag", "-a"),
    ergaenze: list[str] = typer.Option([], "--ergaenze", "-e", help="TYP=Wert zusätzlich anonymisieren"),
    ohne: list[str] = typer.Option([], "--ohne", help="TYP=Wert nicht anonymisieren"),
    anzeigen: bool = typer.Option(False, "--anzeigen", help="Anonymisierten Text ausgeben"),
    docx_ausgabe: Optional[Path] = typer.Option(None, "--docx", help="Anonyme DOCX formatgetreu schreiben"),
    konfig: Optional[Path] = KONFIG,
):
    """Nur erkennen und anonymisieren – nichts wird gesendet."""
    v = _vorbereiten(datei, auftrag, ergaenze, ohne, konfig)
    if anzeigen:
        typer.secho("\n== Anonymisierter Text ==", bold=True)
        typer.echo(v.auftrag_anonym + ("\n\n" if v.auftrag_anonym else "") + v.dokument_anonym)
    if docx_ausgabe:
        _bericht("Anonyme DOCX", v.anonyme_docx_speichern(docx_ausgabe))
        typer.echo(f"Geschrieben: {docx_ausgabe}")
    raise typer.Exit(0 if v.bericht_vorher.gruen else 1)


@app.command()
def bearbeiten(
    datei: Optional[Path] = typer.Argument(None, exists=True, help="DOCX, PDF oder TXT (weglassen = neuen Vertrag erstellen)"),
    auftrag: str = typer.Option(..., "--auftrag", "-a", help="Was Claude tun soll"),
    ergaenze: list[str] = typer.Option([], "--ergaenze", "-e", help="TYP=Wert zusätzlich anonymisieren"),
    ohne: list[str] = typer.Option([], "--ohne", help="TYP=Wert nicht anonymisieren"),
    ja: bool = typer.Option(False, "--ja", "-y", help="Ohne Rückfrage senden"),
    ausgabe: Optional[Path] = typer.Option(None, "--ausgabe", "-o", help="Zielordner"),
    konfig: Optional[Path] = KONFIG,
):
    """Anonymisieren → Claude → Rückanonymisierung → DOCX."""
    v = _vorbereiten(datei, auftrag, ergaenze, ohne, konfig)
    if not v.bericht_vorher.gruen:
        typer.secho("Versand gesperrt. Bitte Funde ergänzen (--ergaenze) und erneut starten.", fg=typer.colors.RED)
        raise typer.Exit(1)
    if not ja and not typer.confirm("\nSind alle Personendaten erfasst? Anonymisierten Text jetzt an Claude senden?"):
        raise typer.Exit(1)
    tresor = Tresor()
    vid = v.im_tresor_ablegen(tresor)
    typer.echo(f"Vorgang {vid} – sende an Claude …")
    try:
        antwort = v.an_claude()
    except ClaudeFehler as fehler:
        typer.secho(str(fehler), fg=typer.colors.RED)
        typer.echo(f"Der anonyme Text liegt im Vorgang {vid}; Antwort später mit 'zurueck {vid} DATEI' einspielen.")
        raise typer.Exit(2)
    tresor.antwort_speichern(vid, antwort)
    bericht = v.zurueck()
    _bericht("Prüfung nach Antwort", bericht)
    ziel = v.ergebnis_speichern(ausgabe or Path(v.konfig["ablage"]["ausgabe"]))
    typer.secho(f"\nErgebnis: {ziel}", bold=True)
    raise typer.Exit(0 if bericht.gruen else 1)


@app.command()
def zurueck(
    vorgang_id: str = typer.Argument(..., help="Vorgangsnummer"),
    datei: Path = typer.Argument(..., exists=True, help="Claude-Antwort (TXT/MD/DOCX) mit Platzhaltern"),
    ausgabe: Optional[Path] = typer.Option(None, "--ausgabe", "-o"),
):
    """Eine Antwort mit Platzhaltern nachträglich zurückanonymisieren (z. B. aus claude.ai kopiert)."""
    tresor = Tresor()
    zuordnung = tresor.laden(vorgang_id)
    text, bericht = pruefung.nach_antwort("", text_laden(datei), zuordnung)
    _bericht("Prüfung nach Antwort", bericht)
    ziel = ausgabe or datei.with_name(f"{datei.stem}_zurueck.docx")
    speichern(text, ziel)
    typer.secho(f"Ergebnis: {ziel}", bold=True)
    raise typer.Exit(0 if bericht.gruen else 1)


@app.command()
def vorgaenge():
    """Gespeicherte Vorgänge auflisten."""
    for vid, angelegt, bezeichnung in Tresor().vorgaenge():
        typer.echo(f"{vid}  {angelegt}  {bezeichnung}")


@app.command()
def typen():
    """Platzhalter-Typen anzeigen."""
    for t, name in TYPEN.items():
        typer.echo(f"{t:14} {name}")


@app.command()
def oberflaeche(port: int = typer.Option(8765, help="Port auf 127.0.0.1"), konfig: Optional[Path] = KONFIG,
                browser: bool = typer.Option(True, help="Browser öffnen")):
    """Weboberfläche mit Prüfansicht starten (nur lokal erreichbar)."""
    import threading
    import webbrowser

    import uvicorn

    from .web import app_erstellen

    if browser:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    uvicorn.run(app_erstellen(konfig_mod.laden(konfig)), host="127.0.0.1", port=port, log_level="warning")


def main():
    app()


if __name__ == "__main__":
    main()
