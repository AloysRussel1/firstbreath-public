# Étape 1 — conventions actuelles, développement uniquement

Les règles des sections 3 et 7 de `shared/CONVENTIONS.md` sont appliquées aux pages 1–48. Les pages 49–80 déjà présentes dans les fichiers restent inchangées : aucune image de test n'a été relue, aucun appel au modèle ni évaluation finale n'a été réalisé.

La branche `ia` contient une référence antérieure à celle travaillée sur `eval`. Les nombres d'environ 46 cases uniques et 26 listes correspondent à l'ensemble historique des dix spécimens ; cette étape traite seulement les six premiers pour respecter le gel du jeu réservé.

Les corrections sont persistantes :

- Cases uniques non cochées : `CONNU false` ; listes de risques ou complications sans objet : `NON_APPLICABLE null`.
- Signes de danger sans case cochée et consultation effectuée : `CONNU []`, selon les lectures du spécimen déjà vérifiées.
- 16 colonnes de visite entièrement vides : les 16 champs de chacune deviennent automatiquement `NON_APPLICABLE null`, soit 256 champs. La géométrie des lignes et le texte du corps du tableau sont utilisés ; une valeur annotée incompatible interrompt l'alignement.
- Niveau d'instruction : `Aucun` aux pages 10 et 26, `Collège` complet à la page 18.
- Antécédents familiaux : `femme : X ; mari : Y` ou `RAS`. La lecture de la page 10 conserve `oncle` en minuscules.
- Indications relues : `Souffrance foetale` (page 12), sans ligature, et `Utérus cicatriciel` complet (page 28).

Les corrections visuelles sont conservées dans les annotations avec leurs références de source. Le générateur applique l'alignement et ne lit que les pages de développement ; il conserve les pages réservées existantes. `aligner_conventions.py` permet aussi de réaligner le corpus sans régénérer ses lectures textuelles.

Le développement contient **1 331 champs annotés sur 1 470 possibles (90,54 %)** et **139 champs en attente**. Sur l'ensemble du fichier conservé : 1 950 champs, 500 en attente. Les vaccins, anomalies et tableaux d'accouchements antérieurs manquants seront traités à l'étape 2. La référence demeure `A_REVISER` ; une validation structurelle ne prouve pas une annotation complète.

Depuis la racine, sous PowerShell :

```powershell
& evaluation/.venv/Scripts/python.exe -B evaluation/verite_terrain.py
& evaluation/.venv/Scripts/python.exe -B shared/valider.py evaluation/verite_terrain.json
& evaluation/.venv/Scripts/python.exe -B -m unittest discover -s evaluation -p 'test_*.py'
```

Résultat attendu : `VALIDE`, 23 tests réussis. La régénération conserve les objets des pages 49–80 à l'identique. Les fichiers `.env`, caches, résultats et aperçus restent locaux, ignorés par Git. Aucun fichier de `data/`, `shared/` ou `extraction/` n'est modifié.
