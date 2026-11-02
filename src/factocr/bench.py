"""Banc d'essai : plusieurs moteurs OCR sur les mêmes factures, plusieurs niveaux de scan.

Pour chaque moteur et chaque sous-dossier (numerique, scan, scan_moyen, scan_fort) :
- temps médian par page ;
- mots retrouvés : F1 entre les mots lus et ceux de la couche texte du PDF d'origine,
  sans tenir compte de l'ordre (les moteurs ne lisent pas un tableau dans le même ordre) ;
- exactitude de l'extraction par règles, champ par champ, et factures entièrement justes.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from factocr.evaluation import charger_verite, evaluer
from factocr.extraction import CHAMPS, extraire
from factocr.ocr import DocumentOCR, fichiers, moteur, ocr_dossier

PONCTUATION = re.compile(r"^[\s:;,.()'\"«»]+|[\s:;,.()'\"«»]+$")


def mots(texte: str) -> Counter[str]:
    return Counter(m for m in (PONCTUATION.sub("", t).casefold() for t in texte.split()) if m)


def f1_mots(reference: str, lu: str) -> float:
    ref, hyp = mots(reference), mots(lu)
    if not ref and not hyp:
        return 1.0
    communs = sum((ref & hyp).values())
    return 2 * communs / (sum(ref.values()) + sum(hyp.values()))


def texte_pdf(chemin: Path) -> str:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(chemin))
    try:
        return "\n".join(p.get_textpage().get_text_range() for p in doc)
    finally:
        doc.close()


def mesurer(
    documents: list[DocumentOCR], references: dict[str, str], verites: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    resultats = []
    f1 = []
    for doc in documents:
        identifiant = Path(doc.fichier).stem
        f1.append(f1_mots(references[identifiant], doc.texte))
        resultats.append(("x", extraire(doc), verites[identifiant]))
    rapport = evaluer(resultats)
    return {
        "factures": len(documents),
        "ms_median": round(statistics.median(p.ms for d in documents for p in d.pages), 1),
        "mots_f1": round(statistics.mean(f1), 4),
        "champs": round(statistics.mean(rapport["exactitude"]["x"][c] for c in CHAMPS), 4),
        "parfaites": rapport["factures_parfaites"]["x"],
        "erreurs": rapport["erreurs"],
    }


def banc(
    donnees: Path, moteurs: list[str], sortie: Path, variantes: list[str]
) -> dict[str, dict[str, Any]]:
    verites = charger_verite(donnees / "verite")
    references = {p.stem: texte_pdf(p) for p in sorted((donnees / "numerique").glob("*.pdf"))}
    resultats: dict[str, dict[str, Any]] = {}
    for nom in moteurs:
        lecteur = moteur(nom, "ocr")
        for variante in variantes:
            dossier = donnees / variante
            if not dossier.is_dir():
                continue
            documents = ocr_dossier(lecteur, donnees, sortie / f"{nom}-ocr", fichiers(dossier))
            resultats.setdefault(nom, {})[variante] = mesurer(documents, references, verites)
    return resultats


def tableau(resultats: dict[str, dict[str, Any]]) -> str:
    lignes = [
        "| Moteur | Documents | Mots retrouvés (F1) | Champs justes | Factures parfaites "
        "| Temps médian / page |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for nom, par_variante in resultats.items():
        for variante, r in par_variante.items():
            lignes.append(
                f"| {nom} | {variante} | {r['mots_f1']:.1%} | {r['champs']:.1%} "
                f"| {r['parfaites']}/{r['factures']} | {r['ms_median']:.0f} ms |"
            )
    return "\n".join(lignes)
