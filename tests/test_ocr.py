from dataclasses import dataclass, field
from pathlib import Path

from factocr.ocr import DocumentOCR, depuis_page_indra, fichiers, ocr_dossier, resume


@dataclass
class FausseLigne:
    box: list[float]
    text: str
    conf: float


@dataclass
class FaussePage:
    lines: list[FausseLigne]
    blocks: list[dict] = field(default_factory=list)
    markdown: str | None = None
    source: str = "ocr"
    note: str = ""
    timings: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n".join(ln.text for ln in self.lines)


def fausse_page() -> FaussePage:
    return FaussePage(
        lines=[
            FausseLigne([10, 20, 200, 40], "FACTURE", 0.99),
            FausseLigne([10, 50, 300, 70], "Total TTC 19 861,14 €", 0.951234),
        ],
        blocks=[{"label": "Section-Header", "bbox": [10, 20, 200, 40], "text": "FACTURE"}],
        markdown="# FACTURE\n\nTotal TTC 19 861,14 €",
    )


class FauxMoteur:
    nom = "faux"

    def lire(self, chemin: Path) -> DocumentOCR:
        return DocumentOCR(chemin.name, self.nom, [depuis_page_indra(0, fausse_page(), 12.0)])


def test_conversion_page_indra():
    p = depuis_page_indra(0, fausse_page(), 123.456)
    assert p.texte == "FACTURE\nTotal TTC 19 861,14 €"
    assert p.lignes[1].confiance == 0.9512
    assert p.blocs[0].type == "Section-Header"
    assert p.ms == 123.5
    assert p.markdown.startswith("# FACTURE")


def test_aller_retour_json():
    doc = DocumentOCR("a.pdf", "indra-auto", [depuis_page_indra(0, fausse_page(), 5.0)])
    relu = DocumentOCR.depuis_json(doc.vers_json())
    assert relu == doc
    assert relu.texte == doc.texte


def test_ocr_dossier_arborescence(tmp_path):
    for sous in ("numerique", "scan"):
        (tmp_path / "in" / sous).mkdir(parents=True)
    (tmp_path / "in" / "numerique" / "f1.pdf").write_bytes(b"%PDF")
    (tmp_path / "in" / "scan" / "f1.png").write_bytes(b"png")
    (tmp_path / "in" / "verite.json").write_text("{}")
    assert len(fichiers(tmp_path / "in")) == 2
    docs = ocr_dossier(FauxMoteur(), tmp_path / "in", tmp_path / "out")
    assert (tmp_path / "out" / "numerique" / "f1.json").exists()
    assert (tmp_path / "out" / "scan" / "f1.json").exists()
    stats = resume(docs)
    assert stats["pages"] == 2 and stats["sources"] == {"ocr": 2}
