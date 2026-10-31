"""Interface en ligne de commande : `factocr --help`."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="Extraction de factures avec Indra OCR.", no_args_is_help=True)
console = Console()


@app.callback()
def principal() -> None:
    """Extraction de factures avec Indra OCR."""


@app.command()
def generer(
    dossier: Path = typer.Option(Path("data"), help="Dossier de sortie."),
    nombre: int = typer.Option(20, min=1, help="Nombre de factures."),
    graine: int = typer.Option(42, help="Graine aléatoire (même graine, mêmes factures)."),
) -> None:
    """Génère des factures synthétiques : PDF, scan simulé et vérité terrain JSON."""
    from factocr.synthese import generer as _generer

    factures = _generer(dossier, nombre, graine)
    console.print(f"[green]{len(factures)} factures écrites dans {dossier}/[/green]")


@app.command()
def ocr(
    entree: Path = typer.Argument(Path("data"), help="Dossier de factures (PDF ou images)."),
    sortie: Path = typer.Option(Path("sorties/ocr"), help="Dossier des JSON."),
    moteur: str = typer.Option("indra", help="Moteur OCR."),
    mode: str = typer.Option(
        "auto", help="auto : couche texte du PDF si elle existe ; ocr : toujours l'OCR."
    ),
) -> None:
    """Lance l'OCR sur un dossier et écrit un JSON normalisé par fichier."""
    import json

    from factocr.ocr import moteur as _moteur
    from factocr.ocr import ocr_dossier, resume

    lecteur = _moteur(moteur, mode)
    documents = ocr_dossier(lecteur, entree, sortie / f"{moteur}-{mode}")
    stats = resume(documents)
    console.print_json(json.dumps(stats, ensure_ascii=False))


@app.command()
def extraire(
    ocr: Path = typer.Argument(..., help="Dossier des JSON OCR (ex. sorties/ocr/indra-ocr)."),
    verite: Path = typer.Option(Path("data/verite"), help="Vérité terrain, pour évaluer."),
    sortie: Path = typer.Option(Path("sorties/extraction"), help="Dossier des résultats."),
) -> None:
    """Extrait les champs par règles et, si la vérité existe, mesure l'exactitude."""
    import json

    from factocr.evaluation import charger_verite, evaluer, tableau_markdown
    from factocr.extraction import extraire as _extraire
    from factocr.ocr import DocumentOCR

    verites = charger_verite(verite) if verite.is_dir() else {}
    resultats = []
    extractions = {}
    for chemin in sorted(ocr.rglob("*.json")):
        doc = DocumentOCR.depuis_json(chemin.read_text(encoding="utf-8"))
        ex = _extraire(doc)
        variante = chemin.parent.name
        extractions[f"{variante}/{chemin.stem}"] = ex.vers_dict()
        if chemin.stem in verites:
            resultats.append((variante, ex, verites[chemin.stem]))

    sortie.mkdir(parents=True, exist_ok=True)
    nom = ocr.name
    (sortie / f"{nom}.json").write_text(
        json.dumps(extractions, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    console.print(f"{len(extractions)} documents extraits -> {sortie / f'{nom}.json'}")
    if resultats:
        rapport = evaluer(resultats)
        (sortie / f"{nom}-evaluation.json").write_text(
            json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        tableau = tableau_markdown(rapport)
        (sortie / f"{nom}-evaluation.md").write_text(tableau + "\n", encoding="utf-8")
        console.print(tableau)
