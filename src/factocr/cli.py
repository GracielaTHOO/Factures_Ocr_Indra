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
