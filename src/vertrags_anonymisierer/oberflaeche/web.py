"""Lokale Weboberfläche (nur 127.0.0.1) mit Prüfansicht."""

from __future__ import annotations

import tempfile
import uuid
from importlib import resources
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from ..claude.auftrag import ClaudeFehler
from ..platzhalter.ersetzen import PlatzhalterKollision
from ..platzhalter.tresor import Tresor
from ..typen import TYPEN
from ..vorgang import Vorgang


def app_erstellen(konfig: dict, client=None) -> FastAPI:
    app = FastAPI(title="Vertrags-Anonymisierer", docs_url=None, redoc_url=None)
    sitzungen: dict[str, Vorgang] = {}
    arbeitsordner = Path(tempfile.mkdtemp(prefix="vertrags-anonymisierer-"))

    def holen(sid: str) -> Vorgang:
        if sid not in sitzungen:
            raise HTTPException(404, "Sitzung abgelaufen – bitte neu laden.")
        return sitzungen[sid]

    def kandidaten(v: Vorgang) -> list[dict]:
        return [k.__dict__ | {"typ_name": TYPEN[k.typ]} for k in v.anonymisierer.kandidatenliste()]

    def vorschau(v: Vorgang) -> dict:
        bericht = v.vorbereiten()
        return {
            "kandidaten": kandidaten(v),
            "auftrag_anonym": v.auftrag_anonym,
            "dokument_anonym": v.dokument_anonym,
            "zuordnung": [{"platzhalter": ph, "wert": e.wert, "typ": TYPEN[e.typ]} for ph, e in v.anonymisierer.zuordnung.items()],
            "bericht": bericht.als_dict(),
        }

    @app.get("/", response_class=HTMLResponse)
    def start() -> str:
        return resources.files(__package__).joinpath("seite.html").read_text(encoding="utf-8")

    @app.get("/api/typen")
    def typen() -> dict:
        return TYPEN

    @app.post("/api/laden")
    async def laden(auftrag: str = Form(""), datei: UploadFile | None = File(None)) -> dict:
        v = Vorgang(konfig)
        pfad = None
        if datei is not None and datei.filename:
            endung = Path(datei.filename).suffix.lower()
            if endung not in {".docx", ".pdf", ".txt", ".md"}:
                raise HTTPException(400, "Bitte DOCX, PDF oder TXT hochladen.")
            pfad = arbeitsordner / f"{uuid.uuid4().hex}{endung}"
            pfad.write_bytes(await datei.read())
        try:
            v.laden(pfad, auftrag)
            if pfad:
                v.dateiname = datei.filename
        except (PlatzhalterKollision, ValueError) as fehler:
            raise HTTPException(400, str(fehler))
        sid = uuid.uuid4().hex
        sitzungen[sid] = v
        return {"sid": sid, **vorschau(v)}

    @app.post("/api/kandidat")
    def kandidat(sid: str = Form(...), typ: str = Form(...), wert: str = Form(...), aktiv: bool = Form(...)) -> dict:
        v = holen(sid)
        v.anonymisierer.setze_aktiv(typ, wert, aktiv)
        return vorschau(v)

    @app.post("/api/ergaenzen")
    def ergaenzen(sid: str = Form(...), typ: str = Form(...), wert: str = Form(...)) -> dict:
        v = holen(sid)
        try:
            v.ergaenze(typ, wert)
        except ValueError as fehler:
            raise HTTPException(400, str(fehler))
        return vorschau(v)

    @app.post("/api/senden")
    def senden(sid: str = Form(...)) -> dict:
        v = holen(sid)
        if not v.vorbereiten().gruen:
            raise HTTPException(409, "Prüfung vor Versand ist rot – Versand gesperrt.")
        tresor = Tresor()
        v.im_tresor_ablegen(tresor)
        try:
            antwort = v.an_claude(client=client)
        except ClaudeFehler as fehler:
            raise HTTPException(502, f"{fehler} (Vorgang {v.vorgang_id})")
        tresor.antwort_speichern(v.vorgang_id, antwort)
        return _rueck(v)

    @app.post("/api/zurueck")
    def zurueck(sid: str = Form(...), antwort: str = Form(...)) -> dict:
        """Rückweg ohne API: Antwort aus claude.ai einfügen."""
        v = holen(sid)
        if not v.zuordnung():
            v.vorbereiten()
        return _rueck(v, antwort)

    def _rueck(v: Vorgang, antwort: str | None = None) -> dict:
        bericht = v.zurueck(antwort)
        ziel = v.ergebnis_speichern(arbeitsordner)
        v._ergebnis_datei = ziel  # type: ignore[attr-defined]
        return {"vorgang": v.vorgang_id, "antwort_anonym": v.antwort_anonym, "ergebnis": v.ergebnis,
                "bericht": bericht.als_dict()}

    @app.get("/api/download/{sid}")
    def download(sid: str):
        v = holen(sid)
        ziel = getattr(v, "_ergebnis_datei", None)
        if not ziel:
            raise HTTPException(404, "Noch kein Ergebnis.")
        return FileResponse(ziel, filename=ziel.name,
                            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    return app
