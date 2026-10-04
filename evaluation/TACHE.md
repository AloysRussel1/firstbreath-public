# Tâche 3 – Correcteur · dossier evaluation/ · branche eval
Points visés : incertitude 20, et tu fais monter l'extraction 30. Ensuite : README et bonus.

## Mission
Mesurer la qualité de l'extraction, dire à la Tâche 2 où elle se trompe, et rendre la confiance fiable.

## Stack et prérequis
- PyMuPDF (`pymupdf`) pour lire la couche texte du PDF (pdftotext n'est pas installé par défaut sous Windows).
- `pandas` pour les tableaux de scores.
- `matplotlib` pour les graphiques.
- `scikit-learn` pour la calibration (`sklearn.calibration.calibration_curve`).
- `rapidfuzz` pour comparer les textes extraits à la vérité terrain.
- Installation : `pip install -r evaluation/requirements.txt -r extraction/requirements.txt`
  (venv activé, depuis la racine ; les dépendances d'extraction servent à appeler extract_page()).
- Les résultats vont dans evaluation/resultats/ (non commité).

## Étapes
1. Vérité terrain : extraire la couche texte de data/Paper Registry/dossiers_specimen_10_patientes.pdf
   (80 pages = 10 patientes x 8 pages) avec PyMuPDF, au format de shared/, validée par shared/valider.py.
2. Annoter à la main ce que le texte ne contient pas (les cases cochées). Lister ce qui reste à annoter.
3. evaluer.py : compare extract_page() à la vérité terrain ; score par champ, par type de page,
   et justesse des statuts. Le tester d'abord avec la fausse extract_page() déjà en place.
4. Dès la livraison de la Tâche 2 (vers H4) : lancer l'évaluation et lui envoyer la liste des champs les plus souvent faux.
5. Confiance finale : plausibilité (plages du schéma, CSV synthétique) et cohérence entre champs
   (parité <= gestité, dates dans le bon ordre…).
6. Graphique de calibration : confiance annoncée vs exactitude réelle (preuve pour le jury).
7. Ensuite : aider au README, puis tableau de bord bonus (agrégats anonymisés à partir du CSV).

## Terminé quand
Un tableau de scores reproductible et un graphique de calibration, relancés après chaque amélioration de la Tâche 2.

## Prompt Claude Code
```
Je travaille dans evaluation/ (branche eval). Lis CLAUDE.md, GUIDE_EQUIPE.md, evaluation/TACHE.md et tout le dossier shared/. Résume ma tâche en 10 lignes, puis attends mon accord. Ensuite réalise les étapes de evaluation/TACHE.md une par une, en t'arrêtant après chacune pour que je teste. La vérité terrain doit passer shared/valider.py. Appelle extract_page() de extraction/pipeline.py sans le modifier. Ne modifie que evaluation/. Je suis sous Windows avec PowerShell.
```
