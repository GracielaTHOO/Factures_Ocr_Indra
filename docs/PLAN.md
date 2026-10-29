# Plan jour par jour (jeudi 29 octobre → mardi 3 novembre 2026)

Objectif de mardi : un test simple et montrable. On lance une commande sur un dossier de
factures, on obtient un CSV des champs extraits et un tableau qui dit, champ par champ, à quel
point Indra fait mieux ou moins bien que Tesseract.

Un commit par jour au minimum, sur `main`, avec une CI verte.

| Jour | Date | Commit(s) visé(s) | Fini quand |
|------|------|-------------------|------------|
| J1 | jeu 29/10 | `feat: squelette du projet et factures synthétiques` | `factocr generer` écrit PDF, scan et JSON ; tests et CI verts |
| J2 | ven 30/10 | `feat(ocr): module Indra et sortie JSON normalisée` + `ci: workflow OCR` | `factocr ocr data/ --moteur indra` produit un JSON par page (texte, lignes, boîtes, blocs, temps) ; le workflow GitHub Actions le lance sur 20 factures et garde les sorties en artefact |
| J3 | sam 31/10 | `feat(extraction): champs par règles et contrôles` | numéro, date, SIRET, TVA, totaux extraits par expressions régulières ; contrôles Luhn, TVA/SIREN et HT + TVA = TTC ; tests sur des textes OCR figés |
| J4 | dim 01/11 | `feat(extraction): extraction par LLM et export CSV` | un LLM local (Qwen2.5 via Ollama, dans la CI) rend un JSON strict ; repli sur les règles si le JSON est invalide ; `factocr extraire` écrit `factures.csv` |
| J5 | lun 02/11 | `feat(bench): Indra contre Tesseract` + `docs: premiers résultats` | temps par page, taux d'erreur caractère et exactitude par champ, sur PDF numériques et scans ; rapport `results/bench.md` généré en CI |
| J6 | mar 03/11 | `feat(demo): mini-interface` + `docs: README final` | interface Gradio : on dépose une facture, on voit les champs et les boîtes surlignées ; README avec résultats et capture ; version 0.1.0 (release créée à la main sur GitHub) |

## Ce qui peut glisser

- Si le LLM en CI est trop lent, J4 se limite aux règles et le LLM passe après mardi.
- Si la démo n'est pas prête mardi, le test simple reste valable sans elle : CSV et benchmark.

## Ensuite

Projet suivant : un RAG sur la création d'entreprise dans la beauté, qui réutilisera le module
OCR de ce dépôt pour lire des guides et documents PDF.

## Contrainte technique

Le conteneur de développement ne peut pas joindre Hugging Face, d'où Indra télécharge ses poids.
Les vrais passages d'Indra se font donc dans GitHub Actions ; les tests unitaires utilisent des
sorties OCR figées.
