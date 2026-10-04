# Étape 4 — annotations du développement terminées

Les patientes 1–6, pages 1–48, ont **1 470 champs annotés sur 1 470 possibles (100 %)**, et **zéro champ non annoté**. Ce total comprend les valeurs lues, les statuts d'absence et les visites sans objet ; il ne signifie pas que toutes les valeurs sont renseignées ni que le modèle est exact à 100 %.

Les 278 champs avec une annotation visuelle persistante sont conservés dans `annotations_manuelles.json`, avec les images sources et leurs empreintes. Le reste provient de la couche texte et des règles automatiques. Une relecture humaine indépendante reste nécessaire : le corpus conserve `A_REVISER`.

## Champs résolus

Après l'étape 1, 139 champs du développement étaient non annotés ; après l'étape 2, il en restait 115. Les deux listes sont conservées dans `annotations_dev_historique.json` pour retracer la couverture.

La relecture des images résout les 115 derniers champs :

- 18 antécédents médicaux, chirurgicaux et gynécologiques des six pages d'antécédents ; les mentions « Aucun » chirurgicales deviennent `RAS`, les mots tronqués sont complétés.
- La région de la page 25 : « Béni Mellal-Khénifra ».
- Les cellules de suivi de grossesse : valeurs visibles, présentation céphalique, col « Ferm » tel qu'écrit, hémoglobines et dates vides `NON_FOURNI null`. Le champ hépatite C, sans résultat ni rubrique sur le formulaire, reste `NON_FOURNI null` ; aucune valeur négative n'est inventée.
- Deux colonnes de visite réellement vides de la page 19 (indices 2 et 6), soit 32 champs `NON_APPLICABLE null`. La détection automatique est corrigée : une lettre italique pouvait déborder vers la colonne voisine. Elle utilise désormais un point intérieur du glyphe. Le développement comprend 18 colonnes de visite entièrement vides.

Les lectures se font sur les images du spécimen, indépendamment des sorties du modèle. Les six pages de grossesse, les antécédents et la région ont été relus dans des aperçus locaux sans identifiants directs. La régénération applique les annotations persistantes et produit automatiquement les compteurs `couverture_dev.json` et la liste `A_ANNOTER_DEV.md`.

## Relecture rapide des cases

Depuis la racine, générer l'interface locale :

```powershell
& evaluation/.venv/Scripts/python.exe -B evaluation/reviser_cases_dev.py
```

Ouvrir `evaluation/apercus/revision_dev/index.html` dans un navigateur. Choisir une page, comparer les zones de cases avec la référence, puis modifier les choix ou le statut. Le bouton **Télécharger les corrections** exporte uniquement les changements explicites dans `corrections_dev.json` ; le navigateur ne modifie pas les fichiers du dépôt.

Le fichier peut être enregistré localement dans `evaluation/apercus/`, puis importé :

```powershell
& evaluation/.venv/Scripts/python.exe -B evaluation/reviser_cases_dev.py --importer evaluation/apercus/corrections_dev.json
& evaluation/.venv/Scripts/python.exe -B evaluation/verite_terrain.py
```

L'import refuse les pages hors 1–48, les corrections dupliquées, les clés hors contrat, les types invalides et les valeurs incompatibles avec les statuts. Il vérifie aussi les empreintes sources avant écriture. Les découpes sont adaptées au spécimen ; elles ne conviennent pas à d'autres formulaires. L'interface n'utilise aucun service externe et ses 48 aperçus restent locaux, ignorés par Git. Pour les textes ou les tableaux, corriger directement les annotations persistantes puis régénérer.

## Tester

```powershell
& evaluation/.venv/Scripts/python.exe -B shared/valider.py evaluation/verite_terrain.json
& evaluation/.venv/Scripts/python.exe -B -m unittest discover -s evaluation -p 'test_*.py'
& evaluation/.venv/Scripts/python.exe -B evaluation/couverture_dev.py
```

Attendu : `VALIDE`, 32 tests réussis, 1 470/1 470 champs et zéro non annoté. Le JavaScript généré passe également la vérification de syntaxe Node.

Les pages de référence et annotations 49–80 sont identiques au commit précédent ; aucun appel au modèle ni évaluation finale n'a été effectué. Les 361 champs encore listés dans `A_ANNOTER.md` appartiennent exclusivement au jeu réservé historique : ils ne sont pas des champs manquants du développement.

Les scores de l'étape 3 portaient sur 1 355 champs. Ils ne décrivent pas cette référence enrichie de 1 470 champs : il faudra relancer la comparaison des pages propres avant de comparer les dégradations ou de calibrer la confiance. Cette étape n'a pas modifié `data/`, `shared/` ou `extraction/`.
