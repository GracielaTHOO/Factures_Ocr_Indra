"""OCR des factures, avec une sortie JSON identique quel que soit le moteur.

Pour chaque fichier (PDF ou image), on écrit un JSON qui contient une entrée par page :
le texte, les lignes avec leur boîte et leur confiance, les blocs de mise en page, le
Markdown quand le moteur en produit, la source (couche texte du PDF ou OCR) et le temps.
L'extraction des champs ne lit que ce format, ce qui permet de comparer les moteurs.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


@dataclass
class LigneOCR:
    boite: list[float]  # x0, y0, x1, y1 en pixels
    texte: str
    confiance: float


@dataclass
class BlocOCR:
    type: str  # Text, Section-Header, Table, Caption…
    boite: list[float]
    texte: str


@dataclass
class PageOCR:
    page: int
    source: str  # ocr | text (couche texte du PDF) | hybrid | error
    texte: str
    lignes: list[LigneOCR] = field(default_factory=list)
    blocs: list[BlocOCR] = field(default_factory=list)
    markdown: str = ""
    ms: float = 0.0
    note: str = ""


@dataclass
class DocumentOCR:
    fichier: str
    moteur: str
    pages: list[PageOCR]

    @property
    def texte(self) -> str:
        return "\n\n".join(p.texte for p in self.pages)

    @property
    def ms(self) -> float:
        return sum(p.ms for p in self.pages)

    def vers_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=1)

    @classmethod
    def depuis_json(cls, texte: str) -> DocumentOCR:
        d = json.loads(texte)
        pages = [
            PageOCR(
                **{
                    **p,
                    "lignes": [LigneOCR(**lg) for lg in p["lignes"]],
                    "blocs": [BlocOCR(**b) for b in p["blocs"]],
                }
            )
            for p in d["pages"]
        ]
        return cls(d["fichier"], d["moteur"], pages)


def depuis_page_indra(index: int, page: Any, ms: float) -> PageOCR:
    """Convertit une `indra_ocr.Page` (lue par attributs, pour pouvoir la simuler en test)."""
    return PageOCR(
        page=index,
        source=page.source,
        texte=page.text,
        lignes=[
            LigneOCR([round(float(v), 1) for v in ln.box], ln.text, round(float(ln.conf), 4))
            for ln in page.lines
        ],
        blocs=[
            BlocOCR(b["label"], [round(float(v), 1) for v in b["bbox"]], b.get("text", ""))
            for b in page.blocks
        ],
        markdown=page.markdown or "",
        ms=round(ms, 1),  # temps mur, rendu du PDF compris, pour comparer les moteurs
        note=page.note,
    )


class MoteurIndra:
    """Indra OCR. Les poids (~76 Mo) sont téléchargés depuis Hugging Face au premier appel."""

    nom = "indra"

    def __init__(self, mode: str = "auto", threads: int = 4, dpi: float = 200.0) -> None:
        import indra_ocr

        self.mode = mode
        self.convertisseur = indra_ocr.load(threads=threads, dpi=dpi, mode=mode)

    def lire(self, chemin: Path) -> DocumentOCR:
        pages = []
        debut = time.perf_counter()
        for i, page in self.convertisseur.convert(chemin):
            fin = time.perf_counter()
            pages.append(depuis_page_indra(i, page, (fin - debut) * 1000))
            debut = fin
        return DocumentOCR(chemin.name, f"{self.nom}-{self.mode}", pages)


class MoteurTesseract:
    """Tesseract 5 (via pytesseract), la référence open source. Les PDF sont rendus en image."""

    nom = "tesseract"

    def __init__(self, langue: str = "fra", dpi: float = 200.0) -> None:
        import pytesseract

        self.pytesseract = pytesseract
        self.langue = langue
        self.dpi = dpi
        self.mode = "ocr"

    def images(self, chemin: Path) -> list[Any]:
        from PIL import Image

        if chemin.suffix.lower() != ".pdf":
            return [Image.open(chemin).convert("L")]
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(str(chemin))
        try:
            return [p.render(scale=self.dpi / 72).to_pil().convert("L") for p in doc]
        finally:
            doc.close()

    def lire(self, chemin: Path) -> DocumentOCR:
        pages = []
        debut = time.perf_counter()
        for i, image in enumerate(self.images(chemin)):
            donnees = self.pytesseract.image_to_data(
                image, lang=self.langue, output_type=self.pytesseract.Output.DICT
            )
            lignes = regrouper_mots(donnees)
            fin = time.perf_counter()
            pages.append(
                PageOCR(
                    page=i,
                    source="ocr",
                    texte="\n".join(lg.texte for lg in lignes),
                    lignes=lignes,
                    ms=round((fin - debut) * 1000, 1),
                )
            )
            debut = fin
        return DocumentOCR(chemin.name, self.nom, pages)


def regrouper_mots(donnees: dict[str, list[Any]]) -> list[LigneOCR]:
    """Les mots de `image_to_data` regroupés en lignes (bloc, paragraphe, ligne)."""
    lignes: dict[tuple[int, int, int], list[int]] = {}
    for i, mot in enumerate(donnees["text"]):
        if str(mot).strip() and float(donnees["conf"][i]) >= 0:
            cle = (donnees["block_num"][i], donnees["par_num"][i], donnees["line_num"][i])
            lignes.setdefault(cle, []).append(i)
    resultat = []
    for indices in lignes.values():
        x0 = min(donnees["left"][i] for i in indices)
        y0 = min(donnees["top"][i] for i in indices)
        x1 = max(donnees["left"][i] + donnees["width"][i] for i in indices)
        y1 = max(donnees["top"][i] + donnees["height"][i] for i in indices)
        confiance = sum(float(donnees["conf"][i]) for i in indices) / len(indices) / 100
        texte = " ".join(str(donnees["text"][i]) for i in indices)
        resultat.append(LigneOCR([x0, y0, x1, y1], texte, round(confiance, 4)))
    return resultat


def moteur(nom: str, mode: str = "auto") -> MoteurIndra | MoteurTesseract:
    if nom == "indra":
        return MoteurIndra(mode=mode)
    if nom == "tesseract":
        return MoteurTesseract()
    raise ValueError(f"moteur inconnu : {nom} (disponibles : indra, tesseract)")


def fichiers(dossier: Path) -> list[Path]:
    return sorted(p for p in dossier.rglob("*") if p.suffix.lower() in EXTENSIONS)


def ocr_dossier(
    lecteur: MoteurIndra | MoteurTesseract,
    entree: Path,
    sortie: Path,
    chemins: Iterable[Path] | None = None,
) -> list[DocumentOCR]:
    """Lit chaque fichier de `entree` et écrit `sortie/<chemin relatif>.json`."""
    documents = []
    for chemin in chemins if chemins is not None else fichiers(entree):
        doc = lecteur.lire(chemin)
        cible = sortie / chemin.relative_to(entree).with_suffix(".json")
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(doc.vers_json(), encoding="utf-8")
        documents.append(doc)
    return documents


def resume(documents: list[DocumentOCR]) -> dict[str, Any]:
    """Statistiques pour le résumé de la CI : pages, temps médian, sources."""
    temps = sorted(p.ms for d in documents for p in d.pages)
    sources: dict[str, int] = {}
    for d in documents:
        for p in d.pages:
            sources[p.source] = sources.get(p.source, 0) + 1
    return {
        "fichiers": len(documents),
        "pages": len(temps),
        "ms_median": temps[len(temps) // 2] if temps else 0.0,
        "ms_total": round(sum(temps), 1),
        "sources": sources,
    }
