# Étape 5 — robustesse aux images dégradées

## Protocole

Les six patientes du développement, pages 1–48, fournissent 48 pages propres et 288 images dégradées : flou, rotation, ombre, sous-exposition (`sombre`), forte compression JPEG et combinaison. Chaque image dégradée utilise **la vérité terrain de sa page originale**. Les pages 49–80 et les vraies photos du registre ne sont pas utilisées.

Le script livré `extraction/degrader.py` est appelé sans modifier son fichier. Comme ses images ne sont pas présentes et que seuls les fichiers de `evaluation/` peuvent être modifiés, son répertoire `SORTIE` est redirigé en mémoire vers `evaluation/degradees/`. Le générateur garde sa graine `firstbreath-degradation-v1`, ses paramètres et son index ; Pillow 12.3.0 a servi à cette génération. Les empreintes des images générées et originales sont vérifiées avant l'évaluation, ainsi que la page, la patiente et le type. Un index incomplet, dupliqué, modifié ou contenant une page réservée est refusé.

`evaluer_degradees.py` appelle directement `extraction.pipeline.extract_page()` et réutilise les mêmes comparaisons que les pages propres. Le type de page est fourni par l'index, comme dans la livraison ; cette expérience mesure la lecture des champs, pas la reconnaissance du type d'une page inconnue. Le cache et les résultats restent dans `evaluation/`, sans changement du pipeline. Les appels aux variantes peuvent être parallèles dans des processus séparés. Les échecs d'appel et champs absents restent dans les dénominateurs.

La couverture des annotations est de **1 470/1 470 champs (100 %)**, dont 1 028 valeurs non nulles. Les valeurs sont comparées avec les tolérances de l'étape 3, les statuts strictement ; un champ entièrement exact doit avoir une valeur correcte et le bon statut. Cette définition inclut les champs sans objet ou non fournis. Les 960 champs de suivi de grossesse représentent 65,3 % du total : le score global n'est pas une moyenne équilibrée des huit types de page. La vérité terrain conserve `A_REVISER` et nécessite une relecture humaine indépendante.

## Reproduire

Depuis la racine, contrôler la génération et les empreintes, sans appeler l'API :

```powershell
& evaluation/.venv/Scripts/python.exe -B evaluation/evaluer_degradees.py --generer-seulement
& evaluation/.venv/Scripts/python.exe -B -m unittest discover -s evaluation -p 'test_*.py'
& evaluation/.venv/Scripts/python.exe -B shared/valider.py evaluation/verite_terrain.json
```

Pour relancer les scores (cache réutilisé ; clé dans `evaluation/.env` requise pour les appels non cachés) :

```powershell
& evaluation/.venv/Scripts/python.exe -B evaluation/evaluer_degradees.py --jobs 3
```

On peut sélectionner un sous-ensemble avec `--pages 1-8`. Il n'existe aucune option permettant d'utiliser le test dans ce script. Les résultats se trouvent dans `evaluation/resultats_degradations_dev/` : `comparaison_degradations.md` et `.json`, puis un sous-dossier par variante avec scores par champ, par type de page, confusion des statuts et comparaisons individuelles. Les empreintes des sources, du générateur, de la référence et du pipeline sont enregistrées dans les scores. Images, résultats détaillés et cache restent hors Git ; les scores agrégés ci-dessous sont versionnés.

## Résultats

| Variante | Sorties valides / 48 | Valeurs | Statuts | Champs entièrement exacts |
|---|---:|---:|---:|---:|
| Propre | 48 | 100,00 % | 98,84 % | 98,84 % |
| Flou | 48 | 85,41 % | 69,80 % | 68,30 % |
| Rotation | 44 | 62,45 % | 54,42 % | 54,22 % |
| Ombre | 48 | 99,90 % | 98,91 % | 98,91 % |
| Sous-exposition | 48 | 99,90 % | 99,32 % | 99,32 % |
| JPEG | 48 | 99,03 % | 98,50 % | 98,23 % |
| Combinaison | 46 | 67,22 % | 53,27 % | 52,38 % |

Les écarts inférieurs à un point pour l'ombre, la sous-exposition et le JPEG ne démontrent pas une amélioration : il s'agit d'une réalisation par image, avec la variabilité du modèle, sur seulement six patientes synthétiques. Le flou réduit nettement la qualité. Le score rotation comprend quatre échecs d'appel du pipeline : 640 champs sont absents et pénalisés. La cause précise de ces exceptions n'est pas identifiée ; le score ne permet pas de les attribuer toutes à une mauvaise lecture visuelle.

Sur les pages propres, les 17 écarts de statut sont 15 valeurs `CONNU` rendues `A_REVISER` et deux absences `NON_FOURNI` rendues `CONNU`. Le score de valeurs à 100 % porte uniquement sur les 1 028 références non nulles ; les valeurs rendues pour des références vides sont pénalisées dans le score de champs entièrement exacts. Un statut de révision prudent reste un désaccord avec la référence, sans être nécessairement une mauvaise lecture.

## Champs entièrement exacts par type de page

| Type | Références | Propre | Flou | Rotation | Ombre | Sous-exposition | JPEG | Combinaison |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ACCOUCHEMENT | 72 | 98,61 % | 77,78 % | 100,00 % | 98,61 % | 98,61 % | 95,83 % | 91,67 % |
| ANTECEDENTS | 138 | 96,38 % | 88,41 % | 99,28 % | 99,28 % | 98,55 % | 99,28 % | 89,86 % |
| GROSSESSE_ACTUELLE | 960 | 99,69 % | 60,83 % | 30,94 % | 99,48 % | 99,79 % | 98,44 % | 34,79 % |
| IDENTIFICATION | 48 | 97,92 % | 89,58 % | 95,83 % | 95,83 % | 97,92 % | 97,92 % | 93,75 % |
| PP_PRECOCE_MERE | 60 | 98,33 % | 75,00 % | 98,33 % | 96,67 % | 98,33 % | 98,33 % | 90,00 % |
| PP_PRECOCE_NOUVEAU_NE | 66 | 98,48 % | 87,88 % | 100,00 % | 100,00 % | 100,00 % | 98,48 % | 81,82 % |
| PP_TARDIF_MERE | 60 | 95,00 % | 81,67 % | 98,33 % | 95,00 % | 98,33 % | 96,67 % | 81,67 % |
| PP_TARDIF_NOUVEAU_NE | 66 | 96,97 % | 71,21 % | 92,42 % | 96,97 % | 96,97 % | 96,97 % | 66,67 % |

Les numérateurs, dénominateurs, scores de valeurs et statuts par type, empreintes et pages en échec sont conservés dans `bilan_degradations_dev.json`, versionné. Le détail par champ demeure dans les résultats locaux.

La rotation a échoué sur les pages 11, 19, 27 et 35. La combinaison a échoué sur les pages 3, 19. Ces appels sont inclus dans les scores ; aucune page de test n’a été évaluée.

Le script produit le bilan même si des appels échouent ; dans ce cas, il renvoie un code de sortie 2 pour signaler des sorties invalides, comme `evaluer.py`.

Vérification : 36 tests passent, le validateur commun accepte la vérité terrain et les 288 empreintes des images dégradées ont été contrôlées. Seul `evaluation/` est modifié. La calibration appartient à l’étape suivante.
