# Étape 6 — calibration et seuil de révision

La recalibration isotone réduit l'ECE sur les patientes 5–6 de **11,76 % à 0,76 %**. Le seuil expérimental recommandé est **1,00 sur la confiance recalibrée**, avec maintien des révisions obligatoires. Sur ces deux patientes, il envoie **2 150/3 430 champs en révision (62,68 %)** et laisse **0 erreur observée sur 1 280 champs non révisés**. Il s'agit d'une recommandation pour le développement ; le pipeline et le seuil partagé de 0,75 ne sont pas modifiés.

## Sources et couverture

`extraction/sorties/<variante>/page_<NN>.json` n'est pas encore livré. Avec l'accord de l'utilisateur, l'analyse utilise les confiances finales du contrat `extract_page()` enregistrées dans les comparaisons de l'étape 5, pour les pages propres et les six dégradations. Les signaux détaillés ne sont pas disponibles et ne sont pas reconstruits ni inventés. Le script acceptera les sorties détaillées lorsqu'elles correspondent exactement aux mêmes prédictions ; des sorties nouvelles nécessitent de relancer l'évaluation dev.

Les sept variantes représentent **10 290 observations de champs**, correspondant aux mêmes 1 470 champs de référence par variante. **9 330 disposent d'une confiance** : 6 060 pour l'apprentissage, 3 270 pour la vérification. Les 960 champs absents à la suite des six échecs du pipeline n'ont aucune confiance : ils sont exclus de l'ECE mais restent dans le dénominateur de révision et sont systématiquement envoyés en révision. Les annotations couvrent 100 % du dev ; leur relecture humaine indépendante reste nécessaire.

## Méthode

La cible est un champ entièrement exact : valeur correcte avec les tolérances de l'étape 3 **et** statut correct. Une valeur bien lue mais rendue `A_REVISER` au lieu de `CONNU` est donc un désaccord. Cette calibration estime la probabilité d'accord complet avec la vérité terrain ; elle ne mesure pas uniquement la transcription.

L'ECE est la moyenne pondérée des écarts absolus entre confiance moyenne et exactitude observée dans dix intervalles de largeur 0,1. Les intervalles vides sont omis, la confiance 1 appartient au dernier intervalle. Le score de Brier mesure l'écart quadratique moyen entre probabilité et exactitude.

La confiance brute, une régression logistique sur la confiance et une régression isotone sont comparées par validation croisée laissant une patiente entière de 1–4 de côté. Toutes ses pages et variantes restent ensemble pour éviter la fuite entre une image propre et ses copies dégradées. La méthode au plus petit Brier est choisie sur cette validation croisée, puis apprise sur toutes les patientes 1–4. Les patientes 5–6 ne servent pas à ajuster la fonction de recalibration.

| Méthode | ECE CV patientes 1–4 | Brier CV patientes 1–4 |
|---|---:|---:|
| Brute | 11,40 % | 0,03876 |
| Logistique | 0,61 % | 0,00808 |
| Isotone retenue | 0,29 % | 0,00731 |

Sur les patientes 5–6, le Brier passe de **0,04913 à 0,01396**. Les paramètres isotones, dénominateurs, métriques par variante et empreintes des sources sont versionnés dans [figures/calibration_dev.json](figures/calibration_dev.json).

![Calibration sur les patientes de vérification](figures/calibration_dev.png)

## Choix du seuil

Les champs absents, sans confiance, de mauvais type de page, ou de statut `A_REVISER`, `ILLISIBLE` ou `INCONNU`, restent en révision. La règle actuelle de confiance finale brute inférieure à 0,75 est également conservée. Parmi les autres champs, une confiance recalibrée **strictement inférieure** au seuil entraîne une révision.

La cible expérimentale est au plus **1 % d'erreurs parmi les champs non révisés pour chacune des sept variantes d'apprentissage**, avec au moins un champ non révisé par variante. Le script choisit le seuil entraînant le moins de révision tout en respectant ce critère sur les patientes 1–4. Un premier critère limité à la moyenne des variantes était trop permissif : il laissait 1,53 % d'erreurs en vérification. Les deux critères ont été explorés pendant le développement ; la vérification actuelle reste exploratoire, et ne constitue pas une évaluation indépendante finale de la politique choisie.

Le seuil retenu **1,00 recalibré** correspond ici au plateau de la régression isotone pour une confiance finale brute **au moins égale à 0,92**, sous réserve des révisions obligatoires. Il ne signifie pas une certitude réelle de 100 %. Sur les patientes 1–4, il révise 59,75 % des champs ; sur les patientes 5–6, 62,68 %. La cible empirique est respectée pour chaque variante de vérification.

| Variante, patientes 5–6 | ECE brute | ECE recalibrée | Champs révisés / 490 | Erreurs / non révisés |
|---|---:|---:|---:|---:|
| Propre | 7,06 % | 0,72 % | 188 | 0 / 302 |
| Flou | 21,86 % | 1,76 % | 398 | 0 / 92 |
| Rotation | 9,63 % | 1,19 % | 362 | 0 / 128 |
| Ombre | 6,41 % | 0,20 % | 155 | 0 / 335 |
| Sous-exposition | 8,64 % | 0,04 % | 359 | 0 / 131 |
| JPEG | 7,09 % | 0,82 % | 228 | 0 / 262 |
| Combinaison | 20,95 % | 1,36 % | 460 | 0 / 30 |

![Charge de révision et erreur résiduelle](figures/compromis_seuil_dev.png)

## Limites et reproduction

Zéro erreur observée n'est pas une garantie : seules deux patientes synthétiques servent à cette vérification, certaines variantes conservent très peu de champs sans révision et les observations partagent leur page originale. Les 10 290 observations ne sont pas 10 290 exemples indépendants. Le score global pondère fortement les pages de grossesse. Les signaux manquants empêchent d'étudier séparément la confiance du modèle, la plausibilité et la cohérence. Aucune page 49–80 n'est utilisée ; l'évaluation finale reste réservée au gel du modèle et à l'autorisation explicite.

Depuis la racine, sans appel API :

```powershell
& evaluation/.venv/Scripts/python.exe -B evaluation/calibrer.py --utiliser-comparaisons
& evaluation/.venv/Scripts/python.exe -B -m unittest discover -s evaluation -p 'test_*.py'
& evaluation/.venv/Scripts/python.exe -B shared/valider.py evaluation/verite_terrain.json
```

Le repli sur les comparaisons exige une option explicite. Les résultats d'étape 5 doivent être présents localement ; le script vérifie la référence, les pages, les clés, les confidences et la cohérence du pipeline et du modèle entre variantes. Les figures PNG et le rapport JSON sont versionnés dans `evaluation/figures/`. Aucun appel réseau, changement de `data/`, de `shared/` ou de `extraction/` n'est nécessaire.
