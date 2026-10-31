"""Extraction des champs d'une facture à partir de la sortie OCR, par règles.

Les règles lisent le texte (expressions régulières tolérantes aux petites erreurs d'OCR)
et, pour les totaux, la géométrie des lignes : sur une facture, le montant est à droite
de son libellé, à la même hauteur, même quand le moteur rend les deux sur des lignes
séparées ou dans un ordre inattendu.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation

from factocr.ocr import DocumentOCR, LigneOCR
from factocr.synthese import luhn_valide, tva_intra

CHAMPS = (
    "numero",
    "date",
    "fournisseur",
    "siret",
    "tva_intra",
    "total_ht",
    "total_tva",
    "total_ttc",
)

MONTANT = re.compile(r"(\d{1,3}(?:[   .]?\d{3})*[.,]\d{2})(?!\d)")
NUMERO = re.compile(r"factur\w*\s*n\s*[°ºo0]?\s*[:.]?\s*([A-Z0-9][A-Z0-9/_-]{2,})", re.I)
DATE = re.compile(r"(\d{2})\s*[/.-]\s*(\d{2})\s*[/.-]\s*(\d{4})")
DATE_LIBELLE = re.compile(r"date\s*(?:de\s+facture|d'émission)?\s*[:.]?\s*" + DATE.pattern, re.I)
SIRET = re.compile(r"siret\s*[:.]?\s*((?:\d[  ]?){13}\d)", re.I)
QUATORZE = re.compile(r"(?<!\d)((?:\d[  ]?){13}\d)(?!\d)")
TVA = re.compile(r"FR\s*([0-9A-Z]{2})\s*((?:\d\s?){8}\d)(?!\d)")
LIBELLES_TOTAUX = {
    "total_ht": re.compile(r"total\s*h\.?\s*t\.?\b", re.I),
    "total_tva": re.compile(r"total\s*t\.?\s*v\.?\s*a\b|montant\s*tva", re.I),
    "total_ttc": re.compile(r"total\s*t\.?\s*t\.?\s*c\b|net\s*à\s*payer", re.I),
}
PAS_UN_FOURNISSEUR = re.compile(r"^(facture|invoice)\b|siret|tva|date|merci|\d{5}", re.I)


@dataclass
class Extraction:
    numero: str | None = None
    date: str | None = None  # AAAA-MM-JJ
    fournisseur: str | None = None
    siret: str | None = None
    tva_intra: str | None = None
    total_ht: str | None = None
    total_tva: str | None = None
    total_ttc: str | None = None
    controles: dict[str, bool | None] = field(default_factory=dict)

    def vers_dict(self) -> dict:
        return asdict(self)


def montant(texte: str) -> Decimal | None:
    """« 1 234,50 € », « 1234.50 » ou « 1.234,50 » -> Decimal("1234.50")."""
    m = MONTANT.search(texte)
    if not m:
        return None
    brut = re.sub(r"[   ]", "", m.group(1))
    entier, dec = brut[:-3], brut[-2:]
    try:
        return Decimal(f"{entier.replace('.', '').replace(',', '')}.{dec}")
    except InvalidOperation:
        return None


def chiffres(texte: str) -> str:
    return re.sub(r"\D", "", texte)


def centre_y(lg: LigneOCR) -> float:
    return (lg.boite[1] + lg.boite[3]) / 2


def total_par_geometrie(lignes: list[LigneOCR], libelle: re.Pattern[str]) -> Decimal | None:
    for lg in lignes:
        m = libelle.search(lg.texte)
        if not m:
            continue
        reste = montant(lg.texte[m.end() :])
        if reste is not None:
            return reste
        hauteur = max(lg.boite[3] - lg.boite[1], 1.0)
        candidats = [
            autre
            for autre in lignes
            if autre is not lg
            and autre.boite[0] >= lg.boite[0]
            and abs(centre_y(autre) - centre_y(lg)) < 0.6 * hauteur
            and montant(autre.texte) is not None
        ]
        if candidats:
            plus_proche = min(candidats, key=lambda a: a.boite[0] - lg.boite[2])
            return montant(plus_proche.texte)
    return None


def total_par_texte(texte: str, libelle: re.Pattern[str]) -> Decimal | None:
    for m in libelle.finditer(texte):
        suite = texte[m.end() : m.end() + 40]
        trouve = montant(suite)
        if trouve is not None:
            return trouve
    return None


def extraire_fournisseur(lignes: list[str]) -> str | None:
    for texte in lignes[:8]:
        propre = texte.strip(" :#*")
        if len(propre) >= 3 and not PAS_UN_FOURNISSEUR.search(propre):
            return propre
    return None


def extraire(doc: DocumentOCR) -> Extraction:
    texte = doc.texte
    lignes = [lg for p in doc.pages[:1] for lg in p.lignes]
    ex = Extraction()

    if m := NUMERO.search(texte):
        ex.numero = m.group(1).rstrip(".-")
    if m := DATE_LIBELLE.search(texte) or DATE.search(texte):
        j, mo, a = m.groups()[-3:]
        ex.date = f"{a}-{mo}-{j}"
    if m := SIRET.search(texte):
        ex.siret = chiffres(m.group(1))
    else:
        valides = [chiffres(c) for c in QUATORZE.findall(texte) if luhn_valide(chiffres(c))]
        ex.siret = valides[0] if valides else None
    if m := TVA.search(texte):
        ex.tva_intra = f"FR{m.group(1)}{chiffres(m.group(2))}"

    textes_lignes = [lg.texte for lg in lignes] or texte.splitlines()
    ex.fournisseur = extraire_fournisseur(textes_lignes)

    for champ, libelle in LIBELLES_TOTAUX.items():
        valeur = total_par_geometrie(lignes, libelle) if lignes else None
        if valeur is None:
            valeur = total_par_texte(texte, libelle)
        setattr(ex, champ, f"{valeur:.2f}" if valeur is not None else None)

    ex.controles = controler(ex)
    return ex


def controler(ex: Extraction) -> dict[str, bool | None]:
    """Contrôles de cohérence ; None quand un champ manque pour conclure."""
    siret_ok = luhn_valide(ex.siret) if ex.siret and len(ex.siret) == 14 else None
    tva_ok = None
    if ex.tva_intra and len(ex.tva_intra) == 13:
        siren = ex.tva_intra[4:]
        tva_ok = ex.tva_intra == tva_intra(siren) and (
            ex.siret is None or ex.siret.startswith(siren)
        )
    totaux_ok = None
    if ex.total_ht and ex.total_tva and ex.total_ttc:
        totaux_ok = Decimal(ex.total_ht) + Decimal(ex.total_tva) == Decimal(ex.total_ttc)
    return {"siret_luhn": siret_ok, "tva_siren": tva_ok, "ht_tva_ttc": totaux_ok}
