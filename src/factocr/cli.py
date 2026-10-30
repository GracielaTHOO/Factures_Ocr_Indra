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
