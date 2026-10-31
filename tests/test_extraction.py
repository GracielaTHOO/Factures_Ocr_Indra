import json
from decimal import Decimal

import pypdfium2 as pdfium
import pytest

from factocr.evaluation import comparer, evaluer, tableau_markdown
from factocr.extraction import CHAMPS, extraire, montant
from factocr.ocr import DocumentOCR, LigneOCR, PageOCR
from factocr.synthese import generer


def doc_texte(texte: str, lignes: list[LigneOCR] | None = None) -> DocumentOCR:
    return DocumentOCR("f.pdf", "test", [PageOCR(0, "ocr", texte, lignes or [])])


def doc_depuis_pdf(chemin) -> DocumentOCR:
    pdf = pdfium.PdfDocument(str(chemin))
    texte = pdf[0].get_textpage().get_text_range()
    pdf.close()
    return doc_texte(texte.replace("\r\n", "\n"))


@pytest.mark.parametrize(
    "brut, attendu",
    [
        ("1 234,50 €", "1234.50"),
        ("19861,14€", "19861.14"),
        ("1.234,50", "1234.50"),
        ("12 500,00 €", "12500.00"),
        ("7,30", "7.30"),
        ("Total TTC : 1 797,74 €", "1797.74"),
    ],
)
def test_montant(brut, attendu):
    assert montant(brut) == Decimal(attendu)


def test_couche_texte_des_pdf_synthetiques(tmp_path):
    factures = generer(tmp_path, nombre=12, graine=3)
    for f in factures:
        ex = extraire(doc_depuis_pdf(tmp_path / "numerique" / f"{f.id}.pdf"))
        verite = json.loads(f.vers_json())
        assert comparer(ex, verite) == dict.fromkeys(CHAMPS, True), f.id
        assert ex.controles == {"siret_luhn": True, "tva_siren": True, "ht_tva_ttc": True}


def test_texte_ocr_bruite():
    texte = (
        "FACTURE\nAtelier Lumière SARL\nFacture no F2026-0042\nDate: 05/03/2026\n"
        "SIRET 235116159 59409\nN° TVA intracommunautaire : FR 88 235116159\n"
        "TotalHT 1 000,00€\nTotal T.V.A 200,00€\nTotal TTC 1200,00 €"
    )
    ex = extraire(doc_texte(texte))
    assert ex.numero == "F2026-0042"
    assert ex.date == "2026-03-05"
    assert ex.fournisseur == "Atelier Lumière SARL"
    assert ex.siret == "23511615959409"
    assert ex.tva_intra == "FR88235116159"
    assert (ex.total_ht, ex.total_tva, ex.total_ttc) == ("1000.00", "200.00", "1200.00")
    assert ex.controles["ht_tva_ttc"] is True


def test_totaux_par_geometrie_quand_les_libelles_sont_groupes():
    # Ordre de lecture en colonnes : tous les libellés, puis tous les montants.
    lignes = [
        LigneOCR([600, 700, 700, 720], "Total HT", 0.9),
        LigneOCR([600, 740, 700, 760], "Total TVA", 0.9),
        LigneOCR([600, 780, 700, 800], "Total TTC", 0.9),
        LigneOCR([900, 701, 1000, 719], "18 063,40 €", 0.9),
        LigneOCR([900, 741, 1000, 759], "1 797,74 €", 0.9),
        LigneOCR([900, 781, 1000, 799], "19 861,14 €", 0.9),
    ]
    texte = "\n".join(lg.texte for lg in lignes)
    ex = extraire(doc_texte(texte, lignes))
    assert (ex.total_ht, ex.total_tva, ex.total_ttc) == ("18063.40", "1797.74", "19861.14")


def test_champs_absents_et_controles_indetermines():
    ex = extraire(doc_texte("Merci de votre confiance."))
    assert all(getattr(ex, c) is None for c in CHAMPS)
    assert ex.controles == {"siret_luhn": None, "tva_siren": None, "ht_tva_ttc": None}


def test_rapport_evaluation(tmp_path):
    f = generer(tmp_path, nombre=1, graine=5)[0]
    verite = json.loads(f.vers_json())
    bon = extraire(doc_depuis_pdf(tmp_path / "numerique" / f"{f.id}.pdf"))
    vide = extraire(doc_texte(""))
    rapport = evaluer([("numerique", bon, verite), ("scan", vide, verite)])
    assert rapport["exactitude"]["numerique"]["total_ttc"] == 1.0
    assert rapport["exactitude"]["scan"]["numero"] == 0.0
    assert rapport["factures_parfaites"] == {"numerique": 1, "scan": 0}
    assert len(rapport["erreurs"]) == len(CHAMPS)
    assert "| **facture entièrement juste** | 1/1 | 0/1 |" in tableau_markdown(rapport)
