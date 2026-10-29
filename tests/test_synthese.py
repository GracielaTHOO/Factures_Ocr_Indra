import json
import random
from decimal import Decimal

import pypdfium2 as pdfium

from factocr.synthese import (
    euros,
    facture_aleatoire,
    generer,
    luhn_valide,
    tva_intra,
)


def test_euros_format_francais():
    assert euros(Decimal("1234.5")) == "1 234,50 €"
    assert euros(Decimal("7")) == "7,00 €"
    assert euros(Decimal("1250000")) == "1 250 000,00 €"


def test_tva_intra_exemple_connu():
    # Exemple publié par l'administration fiscale : SIREN 404833048 -> FR83404833048
    assert tva_intra("404833048") == "FR83404833048"


def test_facture_coherente():
    rng = random.Random(0)
    for i in range(50):
        f = facture_aleatoire(rng, i)
        assert luhn_valide(f.siret) and luhn_valide(f.siret[:9])
        assert f.tva_intra == tva_intra(f.siret[:9])
        ht = sum(Decimal(lg.montant_ht) for lg in f.lignes)
        assert Decimal(f.total_ht) == ht
        assert Decimal(f.total_ttc) == Decimal(f.total_ht) + Decimal(f.total_tva)


def test_generer_reproductible(tmp_path):
    a = generer(tmp_path / "a", nombre=3, graine=7)
    b = generer(tmp_path / "b", nombre=3, graine=7)
    assert [f.vers_json() for f in a] == [f.vers_json() for f in b]
    verite = json.loads((tmp_path / "a" / "verite" / "facture_001.json").read_text())
    assert verite["numero"] == a[0].numero
    assert (tmp_path / "a" / "scan" / "facture_003.png").stat().st_size > 10_000


def test_pdf_contient_les_champs(tmp_path):
    f = generer(tmp_path, nombre=1, graine=1)[0]
    doc = pdfium.PdfDocument(str(tmp_path / "numerique" / f"{f.id}.pdf"))
    texte = doc[0].get_textpage().get_text_range()
    doc.close()
    assert f.numero in texte
    assert f.tva_intra in texte
    assert euros(Decimal(f.total_ttc)) in texte
