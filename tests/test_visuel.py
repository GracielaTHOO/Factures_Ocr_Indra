import pytest
from PIL import Image

from factocr.demo import Analyseur, resume_controles, tableau_champs
from factocr.extraction import extraire
from factocr.ocr import DocumentOCR, LigneOCR, PageOCR
from factocr.visuel import annoter, lignes_sources

LIGNES = [
    LigneOCR([10, 10, 300, 40], "Nettoyage Pro Ouest SARL", 0.99),
    LigneOCR([10, 50, 300, 70], "SIRET : 235 116 159 59409", 0.99),
    LigneOCR([10, 80, 400, 100], "N° TVA intracommunautaire : FR88235116159", 0.99),
    LigneOCR([500, 50, 700, 70], "Facture n° F2026-1140", 0.99),
    LigneOCR([500, 80, 700, 100], "Date : 24/08/2026", 0.99),
    LigneOCR([500, 300, 600, 320], "Total HT", 0.99),
    LigneOCR([650, 300, 780, 320], "18 063,40 €", 0.99),
    LigneOCR([500, 330, 600, 350], "Total TVA", 0.99),
    LigneOCR([650, 330, 780, 350], "1 797,74 €", 0.99),
    LigneOCR([500, 360, 600, 380], "Total TTC", 0.99),
    LigneOCR([650, 360, 780, 380], "19 861,14 €", 0.99),
    LigneOCR([10, 500, 300, 520], "Paiement à 30 jours.", 0.99),
]
DOC = DocumentOCR(
    "f.png", "indra-ocr", [PageOCR(0, "ocr", "\n".join(lg.texte for lg in LIGNES), LIGNES)]
)


def test_chaque_champ_retrouve_sa_ligne():
    sources = lignes_sources(extraire(DOC), LIGNES)
    assert sources == {
        0: "fournisseur",
        1: "siret",
        2: "tva_intra",
        3: "numero",
        4: "date",
        6: "total_ht",
        8: "total_tva",
        10: "total_ttc",
    }


def test_annotation_colore_les_sources():
    image = Image.new("RGB", (800, 560), "white")
    annotee = annoter(image, LIGNES, extraire(DOC))
    assert annotee.size == image.size
    assert annotee.getpixel((8, 30)) != (255, 255, 255)  # cadre du fournisseur
    assert image.getpixel((8, 30)) == (255, 255, 255)  # l'original n'est pas modifié


def test_sorties_de_la_demo():
    ex = extraire(DOC)
    assert tableau_champs(ex)[0] == ["Numéro", "F2026-1140"]
    texte = resume_controles(ex, DOC, 0.25)
    assert "✅ HT + TVA = TTC" in texte and "indra-ocr · OCR · 0.25 s" in texte
    assert Analyseur()(None, "indra", "ocr")[2].startswith("Déposez")


def test_interface_gradio_se_construit():
    pytest.importorskip("gradio")
    from factocr.demo import construire

    assert construire() is not None
