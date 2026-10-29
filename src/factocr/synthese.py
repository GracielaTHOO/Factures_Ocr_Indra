"""Factures françaises synthétiques avec leur vérité terrain.

Chaque facture existe en deux versions :
- « numerique » : un PDF avec couche texte, comme une facture exportée d'un logiciel ;
- « scan » : une image PNG dégradée (légère rotation, flou, bruit), comme une facture
  imprimée puis numérisée.

Les entreprises, numéros et montants sont fictifs. Les SIRET passent la clé de Luhn
et les numéros de TVA intracommunautaire sont calculés à partir du SIREN, pour que
les contrôles de cohérence de l'extraction aient un sens.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from PIL import Image, ImageFilter

FOURNISSEURS = [
    ("Atelier Lumière SARL", "12 rue des Lilas", "69003 Lyon"),
    ("Cosméto Bio SAS", "4 avenue Jean Jaurès", "31000 Toulouse"),
    ("Papeterie du Centre EURL", "27 place du Marché", "45000 Orléans"),
    ("InfoServ Conseil SAS", "88 boulevard Haussmann", "75008 Paris"),
    ("Boulangerie Martin", "3 rue de la Gare", "35000 Rennes"),
    ("Nettoyage Pro Ouest SARL", "15 allée des Pins", "44300 Nantes"),
    ("Studio Graphique Nova", "9 quai de la Fosse", "33000 Bordeaux"),
    ("Fournitures Médicales Duval SA", "52 rue Nationale", "59000 Lille"),
]

CLIENTS = [
    ("Institut Belle Peau", "6 rue Victor Hugo", "13001 Marseille"),
    ("Cabinet Leroy & Associés", "21 rue de Metz", "67000 Strasbourg"),
    ("Salon Coiffure Élégance", "40 cours Mirabeau", "13100 Aix-en-Provence"),
    ("Mairie de Saint-Aubin", "1 place de la Mairie", "76410 Saint-Aubin"),
    ("Vindex Logistique SAS", "7 rue de l'Industrie", "38000 Grenoble"),
]

ARTICLES = [
    ("Crème hydratante 50 ml", Decimal("12.90"), Decimal("20")),
    ("Prestation de conseil (heure)", Decimal("85.00"), Decimal("20")),
    ("Ramette papier A4 80 g", Decimal("4.75"), Decimal("20")),
    ("Maintenance poste informatique", Decimal("120.00"), Decimal("20")),
    ("Pain de campagne 1 kg", Decimal("4.20"), Decimal("5.5")),
    ("Nettoyage des locaux (forfait)", Decimal("340.00"), Decimal("20")),
    ("Création de logo", Decimal("450.00"), Decimal("20")),
    ("Gants nitrile (boîte de 100)", Decimal("7.30"), Decimal("20")),
    ("Travaux de rénovation énergétique", Decimal("1250.00"), Decimal("5.5")),
    ("Livraison", Decimal("15.00"), Decimal("20")),
    ("Repas traiteur (couvert)", Decimal("24.50"), Decimal("10")),
    ("Shampooing professionnel 1 L", Decimal("18.60"), Decimal("20")),
]

CENT = Decimal("0.01")


def arrondi(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def euros(x: Decimal) -> str:
    """1234.5 -> « 1 234,50 € », le format français usuel."""
    entier, dec = f"{arrondi(x):.2f}".split(".")
    groupes = []
    while len(entier) > 3:
        groupes.insert(0, entier[-3:])
        entier = entier[:-3]
    groupes.insert(0, entier)
    return f"{' '.join(groupes)},{dec} €"


def cle_luhn(chiffres: str) -> int:
    """Chiffre à ajouter pour que la chaîne passe la clé de Luhn."""
    total = 0
    for i, c in enumerate(reversed(chiffres)):
        d = int(c)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - total % 10) % 10


def luhn_valide(chiffres: str) -> bool:
    return chiffres.isdigit() and cle_luhn(chiffres[:-1]) == int(chiffres[-1])


def tva_intra(siren: str) -> str:
    cle = (12 + 3 * (int(siren) % 97)) % 97
    return f"FR{cle:02d}{siren}"


def siret_aleatoire(rng: random.Random) -> str:
    base = "".join(str(rng.randint(0, 9)) for _ in range(8))
    siren = base + str(cle_luhn(base))
    nic = "".join(str(rng.randint(0, 9)) for _ in range(4))
    return nic_complete(siren, nic)


def nic_complete(siren: str, nic: str) -> str:
    return siren + nic + str(cle_luhn(siren + nic))


@dataclass
class Ligne:
    description: str
    quantite: int
    prix_unitaire_ht: str
    taux_tva: str
    montant_ht: str


@dataclass
class Facture:
    id: str
    numero: str
    date: str
    fournisseur: str
    fournisseur_adresse: str
    siret: str
    tva_intra: str
    client: str
    client_adresse: str
    lignes: list[Ligne] = field(default_factory=list)
    total_ht: str = "0.00"
    total_tva: str = "0.00"
    total_ttc: str = "0.00"
    gabarit: str = "classique"

    def vers_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def facture_aleatoire(rng: random.Random, index: int) -> Facture:
    nom, rue, ville = rng.choice(FOURNISSEURS)
    client, crue, cville = rng.choice(CLIENTS)
    siret = siret_aleatoire(rng)
    jour = date(2026, 1, 1) + timedelta(days=rng.randint(0, 290))
    lignes = []
    tva_totale = Decimal("0")
    for desc, pu, taux in rng.sample(ARTICLES, rng.randint(1, 6)):
        qte = rng.randint(1, 12)
        ht = arrondi(pu * qte)
        tva_totale += ht * taux / 100
        lignes.append(Ligne(desc, qte, f"{pu:.2f}", f"{taux}", f"{ht:.2f}"))
    total_ht = sum((Decimal(lg.montant_ht) for lg in lignes), Decimal("0"))
    total_tva = arrondi(tva_totale)
    return Facture(
        id=f"facture_{index:03d}",
        numero=f"F{jour.year}-{rng.randint(1, 9999):04d}",
        date=jour.isoformat(),
        fournisseur=nom,
        fournisseur_adresse=f"{rue}, {ville}",
        siret=siret,
        tva_intra=tva_intra(siret[:9]),
        client=client,
        client_adresse=f"{crue}, {cville}",
        lignes=lignes,
        total_ht=f"{total_ht:.2f}",
        total_tva=f"{total_tva:.2f}",
        total_ttc=f"{total_ht + total_tva:.2f}",
        gabarit=rng.choice(["classique", "moderne"]),
    )


def date_fr(iso: str) -> str:
    a, m, j = iso.split("-")
    return f"{j}/{m}/{a}"


def siret_espace(siret: str) -> str:
    return f"{siret[:3]} {siret[3:6]} {siret[6:9]} {siret[9:]}"


def dessiner_pdf(f: Facture, chemin: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    larg, haut = A4
    c = canvas.Canvas(str(chemin), pagesize=A4)
    c.setTitle(f"Facture {f.numero}")
    marge = 50
    moderne = f.gabarit == "moderne"

    if moderne:
        c.setFillColorRGB(0.15, 0.25, 0.45)
        c.rect(0, haut - 90, larg, 90, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 22)
        c.drawString(marge, haut - 55, f.fournisseur)
        c.setFillColorRGB(0, 0, 0)
        y = haut - 120
    else:
        c.setFont("Helvetica-Bold", 16)
        c.drawString(marge, haut - 60, f.fournisseur)
        y = haut - 80

    c.setFont("Helvetica", 10)
    for texte in (
        f.fournisseur_adresse,
        f"SIRET : {siret_espace(f.siret)}",
        f"N° TVA intracommunautaire : {f.tva_intra}",
    ):
        c.drawString(marge, y, texte)
        y -= 14

    c.setFont("Helvetica-Bold", 20 if moderne else 18)
    c.drawRightString(larg - marge, haut - (130 if moderne else 60), "FACTURE")
    c.setFont("Helvetica", 10)
    yd = haut - (150 if moderne else 80)
    c.drawRightString(larg - marge, yd, f"Facture n° {f.numero}")
    c.drawRightString(larg - marge, yd - 14, f"Date : {date_fr(f.date)}")

    y -= 30
    c.setFont("Helvetica-Bold", 11)
    c.drawString(larg / 2, y, "Facturé à :")
    c.setFont("Helvetica", 10)
    c.drawString(larg / 2, y - 14, f.client)
    c.drawString(larg / 2, y - 28, f.client_adresse)

    y -= 70
    cols = [marge, 300, 360, 430, larg - marge]
    entetes = ["Désignation", "Qté", "PU HT", "TVA", "Montant HT"]
    c.setFont("Helvetica-Bold", 10)
    if moderne:
        c.setFillColorRGB(0.9, 0.92, 0.96)
        c.rect(marge - 4, y - 5, larg - 2 * marge + 8, 18, fill=1, stroke=0)
        c.setFillColorRGB(0, 0, 0)
    for i, e in enumerate(entetes):
        if i == 0:
            c.drawString(cols[0], y, e)
        else:
            c.drawRightString(cols[i] + (0 if i == 4 else 40), y, e)
    if not moderne:
        c.line(marge, y - 6, larg - marge, y - 6)
    y -= 22
    c.setFont("Helvetica", 10)
    for lg in f.lignes:
        c.drawString(cols[0], y, lg.description)
        c.drawRightString(cols[1] + 40, y, str(lg.quantite))
        c.drawRightString(cols[2] + 40, y, euros(Decimal(lg.prix_unitaire_ht)))
        c.drawRightString(cols[3] + 40, y, f"{lg.taux_tva.replace('.', ',')} %")
        c.drawRightString(cols[4], y, euros(Decimal(lg.montant_ht)))
        y -= 18
    c.line(marge, y + 8, larg - marge, y + 8)

    y -= 20
    for libelle, montant, gras in (
        ("Total HT", f.total_ht, False),
        ("Total TVA", f.total_tva, False),
        ("Total TTC", f.total_ttc, True),
    ):
        c.setFont("Helvetica-Bold" if gras else "Helvetica", 11 if gras else 10)
        c.drawRightString(larg - marge - 110, y, libelle)
        c.drawRightString(larg - marge, y, euros(Decimal(montant)))
        y -= 18

    c.setFont("Helvetica", 8)
    c.drawString(
        marge,
        40,
        "Paiement à 30 jours. Pénalités de retard : 3 fois le taux d'intérêt légal. "
        "Indemnité forfaitaire de recouvrement : 40 €.",
    )
    c.save()


def simuler_scan(pdf: Path, png: Path, rng: random.Random, dpi: int = 150) -> None:
    """Rend la page en image puis la dégrade comme une numérisation de bureau."""
    import numpy as np
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf))
    try:
        img = doc[0].render(scale=dpi / 72).to_pil().convert("L")
    finally:
        doc.close()
    img = img.rotate(rng.uniform(-1.5, 1.5), resample=Image.BICUBIC, expand=True, fillcolor=255)
    img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 0.8)))
    tableau = np.asarray(img, dtype=np.float32)
    bruit = np.random.default_rng(rng.randint(0, 2**32 - 1)).normal(0, 8, tableau.shape)
    tableau = np.clip(tableau * rng.uniform(0.92, 1.0) + bruit, 0, 255).astype(np.uint8)
    Image.fromarray(tableau).save(png)


def generer(dossier: Path, nombre: int = 20, graine: int = 42) -> list[Facture]:
    """Écrit `nombre` factures dans `dossier` : PDF, PNG scanné et JSON de vérité terrain."""
    rng = random.Random(graine)
    for sous in ("numerique", "scan", "verite"):
        (dossier / sous).mkdir(parents=True, exist_ok=True)
    factures = []
    for i in range(1, nombre + 1):
        f = facture_aleatoire(rng, i)
        pdf = dossier / "numerique" / f"{f.id}.pdf"
        dessiner_pdf(f, pdf)
        simuler_scan(pdf, dossier / "scan" / f"{f.id}.png", rng)
        (dossier / "verite" / f"{f.id}.json").write_text(f.vers_json(), encoding="utf-8")
        factures.append(f)
    return factures
