import csv
import json
from pathlib import Path

from factocr import llm
from factocr.evaluation import comparer
from factocr.export import ecrire_csv
from factocr.extraction import extraire
from factocr.ocr import DocumentOCR, PageOCR

TEXTE = (Path(__file__).parent / "fixtures" / "indra_scan_facture_002.txt").read_text()
DOC = DocumentOCR("facture_002.png", "indra-ocr", [PageOCR(0, "ocr", TEXTE)])
VERITE = {
    "id": "facture_002",
    "numero": "F2026-1140",
    "date": "2026-08-24",
    "fournisseur": "Nettoyage Pro Ouest SARL",
    "siret": "23511615959409",
    "tva_intra": "FR88235116159",
    "total_ht": "18063.40",
    "total_tva": "1797.74",
    "total_ttc": "19861.14",
    "lignes": [
        {
            "description": "Prestation de conseil (heure)",
            "quantite": 11,
            "prix_unitaire_ht": "85.00",
            "taux_tva": "20",
            "montant_ht": "935.00",
        },
        {
            "description": "Pain de campagne 1 kg",
            "quantite": 4,
            "prix_unitaire_ht": "4.20",
            "taux_tva": "5.5",
            "montant_ht": "16.80",
        },
    ],
}


def reponse(**changements):
    base = {k: VERITE[k] for k in VERITE if k != "id"}
    base["lignes"] = [
        {**VERITE["lignes"][1], "taux_tva": "5,5", "prix_unitaire_ht": "4,2"},
        {**VERITE["lignes"][0], "taux_tva": 20},
    ]
    base.update(changements)
    return json.dumps(base)


def test_reponse_parfaite_du_llm():
    ex = llm.fusionner(reponse(siret="235 116 159 59409"), extraire(DOC))
    assert ex.methode == "llm"
    assert all(comparer(ex, VERITE).values())
    assert ex.lignes[0] == VERITE["lignes"][1]


def test_champ_manquant_complete_par_les_regles():
    ex = llm.fusionner(reponse(numero=None, date="24/08/2026"), extraire(DOC))
    assert ex.methode == "llm+regles"
    assert (ex.numero, ex.date) == ("F2026-1140", "2026-08-24")


def test_totaux_incoherents_remplaces_par_ceux_des_regles():
    ex = llm.fusionner(reponse(total_ttc="19961.14"), extraire(DOC))
    assert ex.total_ttc == "19861.14"
    assert ex.controles["ht_tva_ttc"] is True
    assert ex.methode == "llm+regles"


def test_reponse_illisible():
    ex = llm.fusionner("désolé, je ne peux pas", extraire(DOC))
    assert ex.methode == "regles" and ex.numero == "F2026-1140"


def test_serveur_injoignable(monkeypatch):
    def panne(*args, **kwargs):
        raise ConnectionRefusedError

    monkeypatch.setattr(llm, "appeler_ollama", panne)
    ex = llm.extraire_llm(DOC, "qwen2.5:3b")
    assert ex.methode == "regles" and ex.total_ttc == "19861.14"


def test_lignes_comparees_sans_tenir_compte_de_l_ordre():
    ex = llm.fusionner(reponse(), extraire(DOC))
    assert comparer(ex, VERITE)["lignes"] is True
    ex.lignes = ex.lignes[:1]
    assert comparer(ex, VERITE)["lignes"] is False


def test_export_csv(tmp_path):
    chemin = tmp_path / "f.csv"
    ecrire_csv({"scan/facture_002": extraire(DOC)}, chemin)
    lignes = list(csv.DictReader(chemin.open(encoding="utf-8-sig"), delimiter=";"))
    assert lignes[0]["total_ttc"] == "19861,14"
    assert lignes[0]["ht_tva_ttc"] == "oui"
    assert lignes[0]["nb_lignes"] == ""
    assert lignes[0]["methode"] == "regles"
