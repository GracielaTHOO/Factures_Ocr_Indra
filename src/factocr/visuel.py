"""Image annotée : les lignes lues par l'OCR, et celles d'où viennent les champs extraits."""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from factocr.extraction import CHAMPS, Extraction, chiffres, montant
from factocr.ocr import LigneOCR

COULEURS = {
    "numero": (214, 39, 40),
    "date": (255, 127, 14),
    "fournisseur": (44, 160, 44),
    "siret": (148, 103, 189),
    "tva_intra": (140, 86, 75),
    "total_ht": (31, 119, 180),
    "total_tva": (23, 190, 207),
    "total_ttc": (227, 119, 194),
}
GRIS = (170, 170, 170)


def page_image(chemin: Path, dpi: float = 200.0) -> Image.Image:
    """Première page en image, à la résolution qu'utilisent les moteurs pour un PDF."""
    if chemin.suffix.lower() != ".pdf":
        return Image.open(chemin).convert("RGB")
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(chemin))
    try:
        return doc[0].render(scale=dpi / 72).to_pil().convert("RGB")
    finally:
        doc.close()


def contient(champ: str, valeur: str, texte: str) -> bool:
    if champ.startswith("total_"):
        return montant(texte) == Decimal(valeur)
    if champ == "siret":
        return valeur in chiffres(texte)
    if champ == "tva_intra":
        return valeur[4:] in chiffres(texte)
    if champ == "date":
        a, m, j = valeur.split("-")
        return re.search(rf"{j}\s*[/.-]\s*{m}\s*[/.-]\s*{a}", texte) is not None
    return valeur.casefold() in texte.casefold()


def lignes_sources(ex: Extraction, lignes: list[LigneOCR]) -> dict[int, str]:
    """Indice de ligne -> champ qu'elle a fourni (premier champ trouvé)."""
    sources: dict[int, str] = {}
    for champ in CHAMPS:
        valeur = getattr(ex, champ)
        if not valeur:
            continue
        for i, lg in enumerate(lignes):
            if i not in sources and contient(champ, valeur, lg.texte):
                sources[i] = champ
                break
    return sources


def annoter(image: Image.Image, lignes: list[LigneOCR], ex: Extraction) -> Image.Image:
    sortie = image.convert("RGB").copy()
    dessin = ImageDraw.Draw(sortie)
    epaisseur = max(2, sortie.width // 600)
    police = ImageFont.load_default(size=max(12, sortie.width // 70))
    sources = lignes_sources(ex, lignes)
    for i, lg in enumerate(lignes):
        if i not in sources:
            dessin.rectangle(lg.boite, outline=GRIS, width=1)
    for i, champ in sources.items():
        x0, y0, x1, y1 = lignes[i].boite
        couleur = COULEURS[champ]
        dessin.rectangle([x0 - 3, y0 - 3, x1 + 3, y1 + 3], outline=couleur, width=epaisseur)
        etiquette = champ.replace("_", " ")
        largeur = dessin.textlength(etiquette, font=police)
        # Étiquette à droite du cadre, ou à gauche si elle sortirait de l'image.
        gauche = x1 + 8 if x1 + 8 + largeur + 6 <= sortie.width else max(0, x0 - largeur - 14)
        haut = (y0 + y1) / 2 - police.size / 2 - 2
        dessin.rectangle([gauche, haut, gauche + largeur + 6, haut + police.size + 4], fill=couleur)
        dessin.text((gauche + 3, haut + 1), etiquette, fill="white", font=police)
    return sortie
