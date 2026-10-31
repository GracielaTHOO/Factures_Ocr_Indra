"""Comparaison des champs extraits avec la vérité terrain des factures synthétiques."""

from __future__ import annotations

import json
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Any

from factocr.extraction import CHAMPS, Extraction


def normaliser(champ: str, valeur: str | None) -> str | None:
    if valeur is None:
        return None
    if champ.startswith("total_"):
        return f"{Decimal(valeur):.2f}"
    if champ == "fournisseur":
        sans_accents = unicodedata.normalize("NFKD", valeur).encode("ascii", "ignore").decode()
        return " ".join(sans_accents.casefold().split())
    return valeur.strip().upper() if champ in ("numero", "tva_intra") else valeur.strip()


def comparer(extraction: Extraction, verite: dict[str, Any]) -> dict[str, bool]:
    return {c: normaliser(c, getattr(extraction, c)) == normaliser(c, verite[c]) for c in CHAMPS}


def evaluer(resultats: list[tuple[str, Extraction, dict[str, Any]]]) -> dict[str, Any]:
    """`resultats` : (variante, extraction, vérité). Renvoie l'exactitude par champ et variante."""
    par_variante: dict[str, dict[str, list[bool]]] = {}
    controles: dict[str, dict[str, list[bool]]] = {}
    erreurs = []
    for variante, ex, verite in resultats:
        scores = comparer(ex, verite)
        for champ, ok in scores.items():
            par_variante.setdefault(variante, {}).setdefault(champ, []).append(ok)
            if not ok:
                erreurs.append(
                    {
                        "facture": verite["id"],
                        "variante": variante,
                        "champ": champ,
                        "attendu": verite[champ],
                        "obtenu": getattr(ex, champ),
                    }
                )
        for nom, ok in ex.controles.items():
            controles.setdefault(variante, {}).setdefault(nom, []).append(ok is True)
    return {
        "exactitude": {
            v: {c: round(sum(oks) / len(oks), 3) for c, oks in champs.items()}
            for v, champs in par_variante.items()
        },
        "factures_parfaites": {
            v: sum(all(comparer(ex, ver).values()) for var, ex, ver in resultats if var == v)
            for v in par_variante
        },
        "nombre": {v: len(next(iter(c.values()))) for v, c in par_variante.items()},
        "controles_ok": {
            v: {n: round(sum(oks) / len(oks), 3) for n, oks in c.items()}
            for v, c in controles.items()
        },
        "erreurs": erreurs,
    }


def tableau_markdown(rapport: dict[str, Any]) -> str:
    variantes = sorted(rapport["exactitude"])
    lignes = [
        "| Champ | " + " | ".join(variantes) + " |",
        "|---|" + "---:|" * len(variantes),
    ]
    for champ in CHAMPS:
        cellules = [f"{rapport['exactitude'][v][champ]:.0%}" for v in variantes]
        lignes.append(f"| {champ} | " + " | ".join(cellules) + " |")
    parfaites = [f"{rapport['factures_parfaites'][v]}/{rapport['nombre'][v]}" for v in variantes]
    lignes.append("| **facture entièrement juste** | " + " | ".join(parfaites) + " |")
    return "\n".join(lignes)


def charger_verite(dossier: Path) -> dict[str, dict[str, Any]]:
    return {
        p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(dossier.glob("*.json"))
    }
