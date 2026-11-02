import shutil

import pytest

from factocr.bench import banc, f1_mots, tableau
from factocr.synthese import generer


def test_f1_mots_ignore_ordre_et_ponctuation():
    assert f1_mots("Total TTC : 1 200,00 €", "1 200,00 € Total TTC") == 1.0
    assert f1_mots("a b c d", "a b") == pytest.approx(2 * 2 / 6)
    assert f1_mots("", "") == 1.0


def test_niveaux_de_scan(tmp_path):
    a = generer(tmp_path / "a", nombre=2, graine=9)
    b = generer(tmp_path / "b", nombre=2, graine=9, niveaux=("moyen", "fort"))
    assert [f.vers_json() for f in a] == [f.vers_json() for f in b]
    assert (tmp_path / "b" / "scan_fort" / "facture_002.png").exists()
    assert not (tmp_path / "a" / "scan_moyen").exists()


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract absent")
def test_banc_tesseract(tmp_path):
    generer(tmp_path / "data", nombre=2, graine=3)
    resultats = banc(tmp_path / "data", ["tesseract"], tmp_path / "out", ["numerique", "scan"])
    r = resultats["tesseract"]["numerique"]
    assert r["factures"] == 2 and r["mots_f1"] > 0.9
    assert "| tesseract | scan |" in tableau(resultats)
