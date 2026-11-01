"""Export des champs extraits en CSV (séparateur « ; », lisible par Excel en français)."""

from __future__ import annotations

import csv
from pathlib import Path

from factocr.extraction import CHAMPS, Extraction

CONTROLES = ("siret_luhn", "tva_siren", "ht_tva_ttc")
COLONNES = ["document", *CHAMPS, "nb_lignes", *CONTROLES, "methode"]


def oui_non(valeur: bool | None) -> str:
    return {True: "oui", False: "non", None: ""}[valeur]


def ecrire_csv(extractions: dict[str, Extraction], chemin: Path) -> None:
    with chemin.open("w", newline="", encoding="utf-8-sig") as f:
        ecrivain = csv.writer(f, delimiter=";")
        ecrivain.writerow(COLONNES)
        for document, ex in extractions.items():
            ecrivain.writerow(
                [
                    document,
                    *[
                        (getattr(ex, c) or "").replace(".", ",")
                        if c.startswith("total_")
                        else getattr(ex, c) or ""
                        for c in CHAMPS
                    ],
                    "" if ex.lignes is None else len(ex.lignes),
                    *[
                        oui_non(ex.controles.get(n))
                        for n in ("siret_luhn", "tva_siren", "ht_tva_ttc")
                    ],
                    ex.methode,
                ]
            )
