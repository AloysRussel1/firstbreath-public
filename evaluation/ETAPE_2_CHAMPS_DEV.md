# Étape 2 — champs manquants du développement

Uniquement les pages 1–48 sont enrichies. Les objets de référence et les annotations des pages 49–80 restent identiques au commit précédent ; aucune évaluation finale n'a été lancée.

- **12 champs de vaccins** : six consultations précoces `CONNU ["BCG", "HB"]` et six tardives `CONNU []`, à partir des lectures visuelles conservées. Les consultations tardives ont eu lieu.
- **6 champs d'anomalie** : `CONNU "RAS"`. L'exclusion liée à l'ancien faux positif du validateur est supprimée.
- **6 listes d'accouchements antérieurs**, comprenant **13 accouchements**, confirmés par les tableaux des pages 2, 10, 18, 26, 34 et 42. Chaque objet contient exactement `date`, `modalite`, `indication_cesarienne`, `complication`, `poids_g`, `complication_nouveau_ne`. Dates ISO, poids entiers, indication absente `null` et complications `RAS` ; ces accouchements sont tous par voie basse.

Les vaccins et les tableaux obstétricaux sont enregistrés dans les annotations persistantes avec les empreintes de source. Le chargeur vérifie aussi les six sous-clés et les types internes des objets ; il rejette notamment un poids booléen ou une date impossible. La régénération ne modifie pas ces lectures manuelles.

Le développement contient **1 355 champs annotés sur 1 470 (92,18 %)** et **115 champs en attente**. Les annotations persistantes du développement comprennent 195 champs. Sur le fichier complet conservé : 1 974 champs, 476 en attente. La couverture du jeu réservé est historique et n'a pas été réévaluée.

```powershell
& evaluation/.venv/Scripts/python.exe -B evaluation/verite_terrain.py
& evaluation/.venv/Scripts/python.exe -B shared/valider.py evaluation/verite_terrain.json
& evaluation/.venv/Scripts/python.exe -B -m unittest discover -s evaluation -p 'test_*.py'
```

Résultat attendu : `VALIDE`, 26 tests réussis. Aucun appel au modèle, changement de `data/`, de `shared/` ou du pipeline n'est nécessaire pour cette étape. Les comparaisons tolérantes et la relance sur le développement attendent l'étape 3.
