"""Regelbasierte Erkennung personenbezogener Daten in deutschen Verträgen.

Alle Muster bleiben innerhalb einer Zeile (kein \\s, das Zeilenumbrüche
einschließt), damit eine Fundstelle nie über eine Absatzgrenze reicht.
"""

from __future__ import annotations

import re

from ..typen import Fund

SZ = " \t\u00a0"  # Leerraumzeichen für Zeichenklassen (auch geschütztes Leerzeichen)
S = f"[{SZ}]"  # Leerraum innerhalb einer Zeile
KL = r"a-zäöüßéèêáàâíìóòôúùçñ"
GR = r"A-ZÄÖÜÉÈÁÀÍÓÚÇ"
WORT = rf"[{GR}][{KL}]+(?:-[{GR}][{KL}]+)*"
PARTIKEL = rf"(?:von{S}+der|von{S}+dem|van{S}+der|van{S}+den|de{S}+la|von|van|vom|de|zu|zur|ten|ter)"
NACHNAME = rf"(?:{PARTIKEL}{S}+)?{WORT}"

MONATE = "Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember"
DATUM = rf"(?:\d{{1,2}}\.{S}?\d{{1,2}}\.{S}?\d{{4}}|\d{{1,2}}\.{S}+(?:{MONATE}){S}+\d{{4}})"

# Großgeschriebene Wörter, die in Verträgen häufig neben Namen stehen, aber
# selbst keine Namen sind.
STOPPWOERTER = {
    "Käufer", "Käuferin", "Käufers", "Verkäufer", "Verkäuferin", "Verkäufers",
    "Erschienene", "Erschienenen", "Beteiligte", "Beteiligten", "Notar", "Notarin",
    "Eigentümer", "Eigentümerin", "Erwerber", "Erwerberin", "Veräußerer", "Veräußerin",
    "Vollmachtgeber", "Vollmachtgeberin", "Bevollmächtigte", "Bevollmächtigter",
    "Schuldner", "Schuldnerin", "Gläubiger", "Gläubigerin", "Darlehensnehmer",
    "Mieter", "Mieterin", "Vermieter", "Vermieterin", "Erblasser", "Erblasserin",
    "Grundstück", "Grundbuch", "Vertrag", "Vertrags", "Urkunde", "Kaufpreis",
    "Gemarkung", "Flur", "Flurstück", "Blatt", "Amtsgericht", "Gesellschaft",
    "Geschäftsführer", "Geschäftsführerin", "Prokurist", "Prokuristin",
    "Ehemann", "Ehefrau", "Eheleute", "Sohn", "Tochter", "Mutter", "Vater",
    "Und", "Der", "Die", "Das", "Den", "Dem", "Des", "Ein", "Eine", "Einer",
    "Herr", "Herrn", "Frau", "Dr", "Prof", "Straße", "Strasse", "Weg",
    "Personalausweis", "Reisepass", "Geburtsdatum", "Staatsangehörigkeit",
    "Deutschland", "Bundesrepublik", "Euro", "EUR", "Nr", "Abs", "Ziffer",
    "Anlage", "Anlagen", "Seite", "Seiten", "Januar", "Februar", "März", "April",
    "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember",
    "Wohnungseigentum", "Teileigentum", "Erbbaurecht", "Grundschuld", "Vollmacht",
    "Vormerkung", "Auflassung", "Kaufvertrag", "Schenkungsvertrag", "Ehevertrag",
    "Testament", "Erbvertrag", "Hiermit", "Sie", "Er", "Ich", "Wir", "Ihr",
}

# Häufige Vornamen (Auswahl) – findet "Hans Müller" auch ohne Anrede.
VORNAMEN = {
    "Alexander", "Andrea", "Andreas", "Angelika", "Anja", "Anna", "Anne", "Annette",
    "Barbara", "Bernd", "Birgit", "Brigitte", "Christa", "Christian", "Christiane",
    "Christina", "Christine", "Christoph", "Claudia", "Daniel", "Daniela", "David",
    "Dennis", "Dieter", "Dirk", "Doris", "Elena", "Elisabeth", "Emma", "Erika", "Erich",
    "Eva", "Felix", "Florian", "Frank", "Franz", "Friedrich", "Gabriele", "Georg",
    "Gerda", "Gerhard", "Gisela", "Gudrun", "Günter", "Günther", "Hannelore", "Hans",
    "Harald", "Hartmut", "Heike", "Heinz", "Helga", "Helmut", "Herbert", "Hildegard",
    "Horst", "Ilse", "Ingrid", "Jan", "Jana", "Jens", "Jörg", "Johann", "Johanna",
    "Johannes", "Jonas", "Josef", "Julia", "Jürgen", "Karin", "Karl", "Katharina",
    "Kerstin", "Klaus", "Lara", "Laura", "Lea", "Leon", "Lena", "Lisa", "Lukas",
    "Manfred", "Manuela", "Marco", "Maria", "Marie", "Mario", "Markus", "Marion",
    "Martin", "Martina", "Matthias", "Max", "Maximilian", "Michael", "Michaela",
    "Monika", "Nadine", "Nicole", "Niklas", "Nina", "Norbert", "Olaf", "Oliver",
    "Paul", "Peter", "Petra", "Philipp", "Rainer", "Ralf", "Regina", "Reinhard",
    "Renate", "Robert", "Roland", "Rolf", "Rosemarie", "Ruth", "Sabine", "Sandra",
    "Sarah", "Sebastian", "Silke", "Simon", "Sophie", "Stefan", "Stefanie",
    "Stephan", "Susanne", "Sven", "Thomas", "Tim", "Tobias", "Torsten", "Udo",
    "Ulrich", "Ulrike", "Ursula", "Ute", "Uwe", "Volker", "Walter", "Werner",
    "Wolfgang", "Yvonne",
}

ANREDE = rf"\b(?:Herrn?|Frau|Notar(?:in)?|Notarvertreter(?:in)?|Notariatsverwalter(?:in)?|Rechtsanwalt|Rechtsanwältin)"
TITEL = rf"(?:(?:Dr|Prof|Dipl\.-[{GR}{KL}]+)\.?(?:{S}?(?:med|jur|rer\.{S}?nat|phil|h\.{S}?c)\.)*{S}+)*"
NAMEN_FOLGE = rf"{WORT}(?:{S}+{WORT}){{0,3}}?(?:{S}+{NACHNAME})?"

MUSTER_ANREDE = re.compile(rf"{ANREDE}{S}+{TITEL}(?P<namen>{WORT}(?:{S}+(?:{PARTIKEL}{S}+)?{WORT}){{0,3}})")
MUSTER_EHELEUTE = re.compile(
    rf"\bEheleute{S}+{TITEL}(?P<v1>{WORT}){S}+und{S}+{TITEL}(?P<v2>{WORT}){S}+(?P<n>{NACHNAME})"
)
_VORNAMEN_RE = "|".join(sorted(VORNAMEN, key=len, reverse=True))
MUSTER_VORNAME = re.compile(
    rf"\b(?P<v>(?:{_VORNAMEN_RE})(?:[- ](?:{_VORNAMEN_RE}))?){S}+(?P<n>{NACHNAME})\b"
)
MUSTER_GEBURTSNAME = re.compile(rf"\bgeb(?:\.|orene|orener|oren){S}+(?P<n>{NACHNAME})\b")
MUSTER_GEBURTSDATUM = re.compile(
    rf"\b(?:geb(?:\.|oren)(?:{S}+am)?|Geburtsdatum:?|\*){S}*(?P<d>{DATUM})"
)
_STRASSEN_ENDUNG = r"(?:straße|strasse|str\.|weg|allee|platz|ring|gasse|damm|ufer|chaussee|pfad|steig|markt|wall|graben|hof|berg|feld|garten)"
_STRASSEN_WORT = r"(?:Straße|Strasse|Str\.|Weg|Allee|Platz|Ring|Gasse|Damm|Ufer|Chaussee|Pfad|Markt|Wall|Graben)"
_STRASSEN_VOR = rf"(?:Am|An{S}+der|An{S}+den|Auf{S}+dem|Auf{S}+der|Im|In{S}+der|Zum|Zur|Alte|Alter|Neue|Neuer|Große|Kleine|Obere|Untere|Hohe|Lange|St\.|Sankt|[{GR}][{KL}]+er)"
HAUSNUMMER = rf"\d{{1,4}}{S}?[a-zA-Z]?(?:{S}?[-–/]{S}?\d{{1,4}}{S}?[a-zA-Z]?)?(?![\d])"
MUSTER_STRASSE = re.compile(
    rf"(?P<s>(?:(?:{_STRASSEN_VOR}){S}+)?(?:[{GR}][{KL}A-ZÄÖÜ-]*{_STRASSEN_ENDUNG}|{_STRASSEN_WORT}|[{GR}][{KL}]+-[{GR}][{KL}]+-{_STRASSEN_WORT}){S}+{HAUSNUMMER})"
)
MUSTER_PLZ_ORT = re.compile(
    rf"(?<![\d.,/])(?:D-)?(?P<plz>\d{{5}}){S}+(?P<ort>{WORT}(?:{S}+(?:am|an{S}+der|im|in{S}+der|bei|ob{S}+der|vor{S}+der){S}+{WORT})?(?:{S}?\([{GR}{KL}.{SZ}]+\))?)"
)
MUSTER_IBAN = re.compile(r"\b(?P<i>[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,4})?)\b")
MUSTER_BIC = re.compile(rf"\bBIC{S}*:?{S}*(?P<b>[A-Z]{{6}}[A-Z0-9]{{2}}(?:[A-Z0-9]{{3}})?)\b")
MUSTER_EMAIL = re.compile(r"\b(?P<e>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
MUSTER_TELEFON = re.compile(
    rf"\b(?:Tel(?:efon)?|Mobil|Handy|Fax|Telefax)\.?{S}*(?:Nr\.?)?{S}*:?{S}*(?P<t>\+?\d[\d{SZ}/()-]{{5,}}\d)"
)
MUSTER_STEUERID = re.compile(
    rf"(?:Steuer-?ID|Steuer-Identifikationsnummer|[Ss]teuerliche{S}+Identifikationsnummer|Identifikationsnummer|IdNr\.?)(?:{S}+lautet)?{S}*:?{S}*(?P<s>\d{{2}}{S}?\d{{3}}{S}?\d{{3}}{S}?\d{{3}})\b"
)
MUSTER_AUSWEIS = re.compile(
    rf"(?:Personalausweis(?:es)?|Reisepass(?:es)?|Ausweis(?:es)?)(?:-?[Nn]ummer|{S}+Nr\.?|{S}+Nummer)?{S}*:?{S}*(?P<a>[A-Z0-9]{{8,10}})\b"
)
MUSTER_URNR = re.compile(
    rf"\b(?:UR|UVZ|URNr|Urkundenrolle)(?:-|{S})?(?:Nr\.?|Nummer)?{S}*:?{S}*(?P<u>\d{{1,5}}{S}?/{S}?\d{{2,4}}(?:{S}?[A-Z]{{1,3}})?)"
)
MUSTER_GRUNDBUCH = re.compile(
    rf"\bGrundbuch(?:{S}+des{S}+Amtsgerichts{S}+{WORT})?{S}+von{S}+(?P<g>{WORT}(?:[{SZ}-]{WORT})*?){S}+(?:Blatt|Bl\.){S}*(?P<b>\d{{1,6}})\b"
)
MUSTER_BLATT = re.compile(rf"\b(?:Blatt|Bl\.){S}*(?P<b>\d{{1,6}})\b")
MUSTER_GEMARKUNG = re.compile(rf"\bGemarkung{S}+(?P<g>{WORT}(?:-{WORT})*)")
MUSTER_FLURSTUECK = re.compile(rf"\bFlurst(?:ück|ücke|ücks|\.)(?:{S}+Nr\.?)?{S}*(?P<f>\d{{1,6}}(?:{S}?/{S}?\d{{1,5}})?)")
MUSTER_FIRMA = re.compile(
    rf"(?P<f>(?:[{GR}0-9][\w&.'-]*{S}+){{1,4}}(?:GmbH{S}+&{S}+Co\.{S}?KG|gGmbH|GmbH|mbH|AG|SE|KG|OHG|GbR|PartG(?:{S}?mbB)?|UG{S}+\(haftungsbeschränkt\)|e\.{S}?K\.|e\.{S}?V\.|eG))(?![\w])"
)
MUSTER_BETRAG = re.compile(rf"(?P<b>\d{{1,3}}(?:\.\d{{3}})*(?:,\d{{2}})?{S}?(?:EUR|€|Euro))")


def iban_gueltig(iban: str) -> bool:
    roh = iban.replace(" ", "").upper()
    if not 15 <= len(roh) <= 34:
        return False
    umgestellt = roh[4:] + roh[:4]
    try:
        zahl = int("".join(str(int(c, 36)) for c in umgestellt))
    except ValueError:
        return False
    return zahl % 97 == 1


def _ist_name(wort: str) -> bool:
    return wort not in STOPPWOERTER and wort.split("-")[0] not in STOPPWOERTER


_SUBSTANTIV_ENDUNGEN = ("ung", "heit", "keit", "schaft", "tum", "nis", "ion", "tät", "ment", "anteil", "recht", "vertrag", "preis", "grundstück", "erklärung")


def _ist_substantiv(wort: str) -> bool:
    w = wort.lower()
    return any(w.endswith(e) for e in _SUBSTANTIV_ENDUNGEN) and wort not in VORNAMEN


def _name_zerlegen(text: str, start: int) -> list[Fund]:
    """Zerlegt "Hans Peter von Müller" in Vorname(n) und Nachname."""
    teile = list(re.finditer(rf"(?:{PARTIKEL}{S}+)?{WORT}", text))
    genitiv = False
    for i, t in enumerate(teile):
        letztes = t.group().split()[-1]
        if _ist_substantiv(letztes) or not _ist_name(letztes):
            teile = teile[:i]
            break
        # "Herrn Müllers Anteil": Genitiv-s vor einem weiteren Wort beendet den Namen.
        if i < len(teile) - 1 and letztes.endswith("s") and letztes not in VORNAMEN and len(letztes) > 3:
            teile = teile[: i + 1]
            genitiv = True
            break
    # Stoppwörter am Ende abschneiden ("Herrn Müller Käufer").
    while teile and not _ist_name(teile[-1].group().split()[-1]):
        teile.pop()
    if not teile:
        return []
    funde: list[Fund] = []
    n = teile[-1]
    n_ende = n.end() - 1 if genitiv else n.end()
    funde.append(Fund(start + n.start(), start + n_ende, "NACHNAME", text[n.start():n_ende]))
    if len(teile) > 1:
        v_start, v_ende = teile[0].start(), teile[-2].end()
        vorname = text[v_start:v_ende]
        if all(_ist_name(w) for w in vorname.split()):
            funde.append(Fund(start + v_start, start + v_ende, "VORNAME", vorname))
    return funde


def erkenne(text: str, betraege: bool = False) -> list[Fund]:
    """Liefert alle Regelfunde (können sich überlappen)."""
    funde: list[Fund] = []

    def gruppe(m: re.Match, name: str, typ: str, sicher: bool = True) -> None:
        funde.append(Fund(m.start(name), m.end(name), typ, m.group(name), "regel", sicher))

    for m in MUSTER_ANREDE.finditer(text):
        funde.extend(_name_zerlegen(m.group("namen"), m.start("namen")))
    for m in MUSTER_EHELEUTE.finditer(text):
        for g in ("v1", "v2"):
            if _ist_name(m.group(g)):
                gruppe(m, g, "VORNAME")
        if _ist_name(m.group("n").split()[-1]):
            gruppe(m, "n", "NACHNAME")
    for m in MUSTER_VORNAME.finditer(text):
        if _ist_name(m.group("n").split()[-1]):
            gruppe(m, "v", "VORNAME")
            gruppe(m, "n", "NACHNAME")
    for m in MUSTER_GEBURTSNAME.finditer(text):
        if _ist_name(m.group("n").split()[-1]):
            gruppe(m, "n", "NACHNAME")
    for m in MUSTER_GEBURTSDATUM.finditer(text):
        gruppe(m, "d", "GEBURTSDATUM")
    for m in MUSTER_STRASSE.finditer(text):
        s = m.group("s")
        erstes = s.split()[0]
        if erstes in STOPPWOERTER:  # "Verkäufer Hauptstraße 5" -> nur "Hauptstraße 5"
            versatz = s.index(erstes) + len(erstes)
            while versatz < len(s) and s[versatz] in " \t ":
                versatz += 1
            funde.append(Fund(m.start("s") + versatz, m.end("s"), "STRASSE", s[versatz:]))
        else:
            gruppe(m, "s", "STRASSE")
    for m in MUSTER_PLZ_ORT.finditer(text):
        gruppe(m, "plz", "PLZ")
        if _ist_name(m.group("ort").split()[0]):
            gruppe(m, "ort", "ORT")
    for m in MUSTER_IBAN.finditer(text):
        if iban_gueltig(m.group("i")):
            gruppe(m, "i", "IBAN")
    for m in MUSTER_BIC.finditer(text):
        gruppe(m, "b", "BIC")
    for m in MUSTER_EMAIL.finditer(text):
        gruppe(m, "e", "EMAIL")
    for m in MUSTER_TELEFON.finditer(text):
        gruppe(m, "t", "TELEFON")
    for m in MUSTER_STEUERID.finditer(text):
        gruppe(m, "s", "STEUERID")
    for m in MUSTER_AUSWEIS.finditer(text):
        if re.search(r"\d", m.group("a")):
            gruppe(m, "a", "AUSWEIS")
    for m in MUSTER_URNR.finditer(text):
        gruppe(m, "u", "URNR")
    for m in MUSTER_GRUNDBUCH.finditer(text):
        gruppe(m, "g", "GEMARKUNG")
    for m in MUSTER_BLATT.finditer(text):
        gruppe(m, "b", "BLATT")
    for m in MUSTER_GEMARKUNG.finditer(text):
        gruppe(m, "g", "GEMARKUNG")
    for m in MUSTER_FLURSTUECK.finditer(text):
        gruppe(m, "f", "FLURSTUECK")
    for m in MUSTER_FIRMA.finditer(text):
        f = m.group("f")
        woerter = list(re.finditer(r"\S+", f))
        # Rollenbezeichnungen, Artikel und Satzreste vorne abschneiden
        # ("Die Verkäuferin Müller Bau GmbH" -> "Müller Bau GmbH").
        while len(woerter) > 2 and (woerter[0].group().rstrip(",") in STOPPWOERTER or woerter[0].group().endswith(",")):
            woerter.pop(0)
        pos = woerter[0].start()
        if len(woerter) >= 2:
            funde.append(Fund(m.start("f") + pos, m.end("f"), "FIRMA", f[pos:]))
    if betraege:
        for m in MUSTER_BETRAG.finditer(text):
            gruppe(m, "b", "BETRAG")
    return [f for f in funde if "\n" not in f.wert and f.wert.strip() == f.wert and f.wert]
