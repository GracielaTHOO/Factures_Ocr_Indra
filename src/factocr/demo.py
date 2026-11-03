"""Mini-démo Gradio : on dépose une facture, on voit les champs et d'où ils viennent."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from factocr.extraction import CHAMPS, Extraction, extraire
from factocr.ocr import DocumentOCR, moteur
from factocr.visuel import annoter, page_image

LIBELLES = {
    "numero": "Numéro",
    "date": "Date",
    "fournisseur": "Fournisseur",
    "siret": "SIRET",
    "tva_intra": "TVA intracommunautaire",
    "total_ht": "Total HT",
    "total_tva": "Total TVA",
    "total_ttc": "Total TTC",
}
CONTROLES = {
    "siret_luhn": "Clé de Luhn du SIRET",
    "tva_siren": "TVA cohérente avec le SIREN",
    "ht_tva_ttc": "HT + TVA = TTC",
}


def tableau_champs(ex: Extraction) -> list[list[str]]:
    return [[LIBELLES[c], getattr(ex, c) or "—"] for c in CHAMPS]


def resume_controles(ex: Extraction, doc: DocumentOCR, secondes: float) -> str:
    symbole = {True: "✅", False: "❌", None: "➖"}
    lignes = [f"- {symbole[ex.controles.get(k)]} {v}" for k, v in CONTROLES.items()]
    page = doc.pages[0] if doc.pages else None
    source = (
        {"text": "couche texte du PDF", "ocr": "OCR"}.get(page.source, page.source) if page else "—"
    )
    lignes.append(f"\n{doc.moteur} · {source} · {secondes:.2f} s")
    return "\n".join(lignes)


class Analyseur:
    """Garde un moteur chargé par nom, pour ne pas recharger les modèles à chaque facture."""

    def __init__(self) -> None:
        self.moteurs: dict[tuple[str, str], Any] = {}

    def __call__(self, chemin: str | None, nom: str, mode: str) -> tuple[Any, ...]:
        if not chemin:
            return None, [], "Déposez une facture (PDF ou image).", ""
        cle = (nom, mode)
        if cle not in self.moteurs:
            self.moteurs[cle] = moteur(nom, mode)
        debut = time.perf_counter()
        doc = self.moteurs[cle].lire(Path(chemin))
        secondes = time.perf_counter() - debut
        ex = extraire(doc)
        lignes = doc.pages[0].lignes if doc.pages else []
        image = annoter(page_image(Path(chemin)), lignes, ex)
        return image, tableau_champs(ex), resume_controles(ex, doc, secondes), doc.texte


def construire(exemples: list[str] | None = None) -> Any:
    import gradio as gr

    analyser = Analyseur()
    with gr.Blocks(title="Factures avec Indra OCR") as app:
        gr.Markdown(
            "# Factures avec Indra OCR\n"
            "Déposez une facture : l'OCR la lit, les règles extraient les champs, "
            "et l'image montre la ligne d'où vient chacun."
        )
        with gr.Row():
            with gr.Column(scale=1):
                fichier = gr.File(label="Facture (PDF, PNG, JPEG)", type="filepath")
                nom = gr.Radio(["indra", "tesseract"], value="indra", label="Moteur")
                mode = gr.Radio(
                    ["auto", "ocr"],
                    value="ocr",
                    label="Mode (Indra)",
                    info="auto lit la couche texte d'un PDF quand elle existe",
                )
                bouton = gr.Button("Analyser", variant="primary")
                champs = gr.Dataframe(headers=["Champ", "Valeur"], label="Champs extraits")
                controles = gr.Markdown()
            with gr.Column(scale=2):
                image = gr.Image(label="Lignes lues et sources des champs", type="pil")
        with gr.Accordion("Texte OCR brut", open=False):
            texte = gr.Textbox(lines=20, show_label=False)
        if exemples:
            gr.Examples(exemples, inputs=[fichier])
        bouton.click(analyser, [fichier, nom, mode], [image, champs, controles, texte])
    return app
