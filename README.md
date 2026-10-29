# Factures_Ocr_Indra

Je m'amuse à tester le nouveau modèle Indra OCR sur des factures.

[Indra OCR](https://github.com/datalab-to/indra) est un modèle OCR d'un million de paramètres
publié par Datalab en octobre 2026. Il tourne sur CPU, sans GPU ni PyTorch, et rend pour chaque
page du Markdown ou du JSON avec les lignes, leurs boîtes et les blocs de mise en page.
Ce dépôt teste s'il suffit pour extraire les champs d'une facture française :
numéro, date, fournisseur, SIRET, TVA intracommunautaire, lignes et totaux.

## Démarche

1. **Factures synthétiques** avec vérité terrain : chaque facture existe en PDF numérique
   (couche texte) et en scan simulé (image légèrement tournée, floue et bruitée).
2. **OCR** avec Indra (et Tesseract pour comparer).
3. **Extraction** des champs, d'abord par règles, puis par un LLM local.
4. **Contrôles** : clé de Luhn du SIRET, cohérence TVA intracommunautaire / SIREN, HT + TVA = TTC.
5. **Mesure** : temps par page et exactitude champ par champ, Indra contre Tesseract.

Le plan jour par jour est dans [docs/PLAN.md](docs/PLAN.md).

## Démarrage

```bash
pip install -e ".[dev]"
factocr generer --nombre 20          # data/numerique, data/scan, data/verite
pytest
```

## Licences

Le code de ce dépôt est sous licence MIT. Le code d'Indra est sous Apache 2.0 ; ses poids sont
sous OpenRAIL-M modifiée, gratuits pour la recherche, l'usage personnel et les structures de moins
de 20 M$ de chiffre d'affaires ou de levée (voir [datalab.to/pricing](https://www.datalab.to/pricing)).
Toutes les factures du dépôt sont fictives.
