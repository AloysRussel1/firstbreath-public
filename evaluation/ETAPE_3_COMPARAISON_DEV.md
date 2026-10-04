# Étape 3 — comparaison et scores du développement

L'évaluateur appelle directement `extraction.pipeline.extract_page()` sans modifier ses sources. Il sélectionne **1–48 par défaut** et refuse toute page 49–80 avant le chargement des images, sauf `--autoriser-test`. Cette option reste réservée au gel du modèle et à l'autorisation explicite de l'utilisateur ; aucun lancement final n'a été effectué.

## Méthode

Les types et statuts restent stricts. Tolérances absolues fixées avant l'exécution : décimaux 0,1 ; poids 10 g ; chaque composante de tension 1 mmHg ; autres entiers exacts. Les textes libres sont comparés avec RapidFuzz `ratio`, seuil 85/100, après normalisation des accents, ligatures (`œ` → `oe`, `æ` → `ae`), casse et espaces. « Ferm » et « Fermé » correspondent.

Les chaînes de moins de quatre caractères, numéros de fiche, choix et dates ne bénéficient pas d'une comparaison floue. Une différence de mots de négation la bloque. Les listes de choix sont comparées sans ordre, sans doublons. Les objets d'accouchement gardent l'ordre, les sous-clés et les dates exactes ; leurs textes sont normalisés et leurs poids bénéficient de la tolérance de 10 g. Une similarité textuelle n'est pas une garantie d'équivalence sémantique.

Les champs entièrement exacts exigent un statut exact et une valeur correcte **selon ces tolérances**, ainsi que le bon type de page. Les valeurs sont évaluées sur les références non nulles ; les champs invalides ou absents comptent comme erreurs. Les champs non annotés sont exclus.

`OBSERVATIONS_BLOQUEES.md` est réécrit en UTF-8, sans accents remplacés par `?`. Les lectures du développement y sont indiquées comme intégrées ; celles du jeu réservé restent historiques, sans nouvelle annotation.

## Résultats du 3 octobre 2026

Fournisseur Anthropic, modèle `claude-sonnet-5`. La relance a réutilisé le cache local des lectures du modèle et appliqué le pipeline et la normalisation actuels à la référence corrigée. Aucun nouvel échantillonnage du modèle n'est revendiqué.

48 sorties valides, aucune anomalie ou erreur d'appel. 36 doublons d'images ignorés. Référence : **1 355/1 470 champs possibles (92,18 %)** ; **115 champs en attente exclus**.

| Mesure globale | Réussites / références | Score |
|---|---:|---:|
| Couverture de l'extraction | 1 355 / 1 355 | 100,00 % |
| Valeurs correctes | 1 002 / 1 002 | 100,00 % |
| Statuts exacts | 1 345 / 1 355 | 99,26 % |
| Champs entièrement exacts | 1 345 / 1 355 | 99,26 % |

Chaque type comprend six pages, avec une couverture d'extraction de 100 %.

| Type de page | Champs | Valeurs | Statuts | Champs entièrement exacts |
|---|---:|---:|---:|---:|
| Identification | 47 | 100,00 % | 100,00 % | 100,00 % |
| Antécédents | 120 | 100,00 % | 98,33 % | 98,33 % |
| Grossesse | 864 | 100,00 % | 100,00 % | 100,00 % |
| Accouchement | 72 | 100,00 % | 98,61 % | 98,61 % |
| Postpartum précoce — mère | 60 | 100,00 % | 98,33 % | 98,33 % |
| Postpartum précoce — nouveau-né | 66 | 100,00 % | 98,48 % | 98,48 % |
| Postpartum tardif — mère | 60 | 100,00 % | 95,00 % | 95,00 % |
| Postpartum tardif — nouveau-né | 66 | 100,00 % | 96,97 % | 96,97 % |

Il reste dix écarts de statut : notamment la planification familiale et les statuts `A_REVISER` pour des lectures dont la valeur est correcte. Un statut prudent différent de la référence compte comme un écart, sans prouver une mauvaise lecture. Le détail figure dans `resultats_etape3_dev/comparaisons.jsonl` et `rapport.md`.

## Tester et reproduire

```powershell
& evaluation/.venv/Scripts/python.exe -B -m unittest discover -s evaluation -p 'test_*.py'
& evaluation/.venv/Scripts/python.exe -B shared/valider.py evaluation/verite_terrain.json
& evaluation/.venv/Scripts/python.exe -B evaluation/evaluer.py --pages 49
```

Attendu : 29 tests réussis, `VALIDE`, puis refus explicite de la page 49 sans appel au pipeline.

Pour relancer uniquement le développement, avec la configuration Anthropic locale :

```powershell
& evaluation/.venv/Scripts/python.exe -B evaluation/evaluer.py --sortie evaluation/resultats_etape3_dev --etiquette ia-etape3-dev
```

Les résultats détaillés restent locaux, ignorés par Git, et contiennent les empreintes du pipeline, du client, de la normalisation, de la référence et des annotations. Le cache du client est redirigé vers `evaluation/cache/` et contient ses lectures intermédiaires ; les rapports de scores ne contiennent pas les valeurs prédites ni les logs bruts. La clé peut être configurée dans `evaluation/.env` ou le `.env` racine ; sans clé, les appels Anthropic ne démarrent pas.

Ces scores concernent un corpus synthétique partiellement annoté. Les nombreuses visites non effectuées influencent les résultats agrégés. Le type des images connues vient de l'index par hash : sa justesse ne mesure pas la détection d'images inconnues. Les images dégradées, la calibration et la mesure finale restent à réaliser aux étapes autorisées suivantes.
