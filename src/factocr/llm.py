"""Extraction des champs par un LLM local (Ollama), avec repli sur les règles.

Le LLM reçoit le texte OCR et doit rendre un JSON qui suit un schéma strict (Ollama le
contraint avec `format`). Chaque champ absent, mal formé ou incohérent est repris de
l'extraction par règles, et `methode` dit d'où vient le résultat :
« llm », « llm+regles » (au moins un champ complété par les règles) ou « regles »
(réponse du LLM inutilisable).
"""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import fields
from decimal import Decimal, InvalidOperation
from typing import Any

from factocr.extraction import CHAMPS, Extraction, controler, extraire
from factocr.ocr import DocumentOCR

MONTANT_JSON = {"type": ["string", "null"], "pattern": r"^-?\d+\.\d{2}$"}
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "numero": {"type": ["string", "null"]},
        "date": {"type": ["string", "null"], "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "fournisseur": {"type": ["string", "null"]},
        "siret": {"type": ["string", "null"], "pattern": r"^\d{14}$"},
        "tva_intra": {"type": ["string", "null"], "pattern": r"^FR[0-9A-Z]{2}\d{9}$"},
        "total_ht": MONTANT_JSON,
        "total_tva": MONTANT_JSON,
        "total_ttc": MONTANT_JSON,
        "lignes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "quantite": {"type": "integer"},
                    "prix_unitaire_ht": MONTANT_JSON,
                    "taux_tva": {"type": "string"},
                    "montant_ht": MONTANT_JSON,
                },
                "required": [
                    "description",
                    "quantite",
                    "prix_unitaire_ht",
                    "taux_tva",
                    "montant_ht",
                ],
            },
        },
    },
    "required": [*CHAMPS, "lignes"],
}

CONSIGNE = """Tu extrais les informations d'une facture française à partir de son texte OCR.
Le texte peut contenir des erreurs de lecture et l'ordre des cellules du tableau peut être
mélangé. Réponds uniquement par un objet JSON avec ces clés :
- numero : le numéro de facture, tel qu'écrit (ex. "F2026-0042")
- date : la date de facture au format AAAA-MM-JJ
- fournisseur : le nom de l'entreprise qui émet la facture (pas le client)
- siret : les 14 chiffres du SIRET du fournisseur, sans espaces
- tva_intra : le numéro de TVA intracommunautaire, sans espaces (ex. "FR88235116159")
- total_ht, total_tva, total_ttc : montants avec un point décimal et deux décimales
  (ex. "1797.74"), sans symbole ni espace
- lignes : une entrée par ligne du tableau, avec description, quantite (entier),
  prix_unitaire_ht et montant_ht (même format que les totaux), taux_tva (ex. "20" ou "5.5")
Mets null pour une information introuvable. N'invente rien."""


def appeler_ollama(
    texte: str, modele: str, url: str = "http://127.0.0.1:11434", delai: float = 300.0
) -> str:
    """Renvoie le contenu brut de la réponse du modèle (normalement du JSON)."""
    charge = {
        "model": modele,
        "messages": [
            {"role": "system", "content": CONSIGNE},
            {"role": "user", "content": texte},
        ],
        "format": SCHEMA,
        "stream": False,
        "options": {"temperature": 0, "num_ctx": 4096},
    }
    requete = urllib.request.Request(
        f"{url}/api/chat",
        data=json.dumps(charge).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(requete, timeout=delai) as reponse:
        return json.loads(reponse.read())["message"]["content"]


def _montant(valeur: Any) -> str | None:
    if valeur is None:
        return None
    try:
        return f"{Decimal(str(valeur).replace(' ', '').replace(',', '.')):.2f}"
    except InvalidOperation:
        return None


def _valide(champ: str, valeur: Any) -> str | None:
    """Normalise une valeur du LLM, ou None si elle n'a pas la forme attendue."""
    if valeur is None or not str(valeur).strip():
        return None
    texte = str(valeur).strip()
    if champ.startswith("total_"):
        return _montant(texte)
    if champ == "date":
        return texte if re.fullmatch(r"\d{4}-\d{2}-\d{2}", texte) else None
    if champ == "siret":
        chiffres = re.sub(r"\D", "", texte)
        return chiffres if len(chiffres) == 14 else None
    if champ == "tva_intra":
        compact = re.sub(r"\s", "", texte).upper()
        return compact if re.fullmatch(r"FR[0-9A-Z]{2}\d{9}", compact) else None
    return texte


def fusionner(reponse: str, regles: Extraction) -> Extraction:
    """Applique la réponse du LLM et complète par les règles champ par champ."""
    try:
        donnees = json.loads(reponse)
        if not isinstance(donnees, dict):
            raise ValueError("pas un objet JSON")
    except (json.JSONDecodeError, ValueError):
        return Extraction(**{f.name: getattr(regles, f.name) for f in fields(regles)})

    ex = Extraction(methode="llm")
    complete = False
    for champ in CHAMPS:
        valeur = _valide(champ, donnees.get(champ))
        if valeur is None and getattr(regles, champ) is not None:
            valeur, complete = getattr(regles, champ), True
        setattr(ex, champ, valeur)
    ex.controles = controler(ex)
    # Totaux incohérents mais cohérents côté règles : on garde ceux des règles.
    if ex.controles["ht_tva_ttc"] is False and regles.controles.get("ht_tva_ttc"):
        ex.total_ht, ex.total_tva = regles.total_ht, regles.total_tva
        ex.total_ttc = regles.total_ttc
        complete = True
        ex.controles = controler(ex)
    lignes = donnees.get("lignes")
    if isinstance(lignes, list):
        ex.lignes = [normaliser_ligne(lg) for lg in lignes if isinstance(lg, dict)]
    ex.methode = "llm+regles" if complete else "llm"
    return ex


def normaliser_ligne(lg: dict[str, Any]) -> dict[str, Any]:
    try:
        quantite = int(lg.get("quantite"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        quantite = None
    taux = _montant(lg.get("taux_tva"))
    return {
        "description": str(lg.get("description", "")).strip(),
        "quantite": quantite,
        "prix_unitaire_ht": _montant(lg.get("prix_unitaire_ht")),
        "taux_tva": taux.rstrip("0").rstrip(".") if taux else None,
        "montant_ht": _montant(lg.get("montant_ht")),
    }


def extraire_llm(doc: DocumentOCR, modele: str, url: str = "http://127.0.0.1:11434") -> Extraction:
    regles = extraire(doc)
    try:
        reponse = appeler_ollama(doc.texte, modele, url)
    except OSError:
        return regles
    return fusionner(reponse, regles)
