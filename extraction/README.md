# FirstBreath — extraction

Pipeline qui transforme la photo d'une page du registre en objet structuré conforme à
[shared/CONTRAT.md](../shared/CONTRAT.md) : un statut et une confiance pour chaque champ du schéma.

```python
from extraction.pipeline import extract_page
extract_page("chemin/page.png")  # {"type_page": "...", "champs": [{champ, valeur, statut, confiance, page_source}]}
```

## Étapes

1. **Type de page** : reconnu par l'empreinte sha256 de l'image (`index.json`). Sinon, il est détecté par
   `claude-haiku-4-5`.
2. **Lecture** par `claude-sonnet-5`, avec un prompt propre à chaque type de page (`prompts.py`, versionné) et une
   sortie forcée par appel d'outil, générée depuis `shared/schema_champs.json` (`schema_outil.py`). Pour chaque
   champ, le modèle rend la valeur, le statut, sa confiance et le texte lu tel quel, dans n'importe quelle
   écriture. Il ne lit jamais un nom, une CIN, un téléphone ni une adresse.
3. **Normalisation** (`normalisation.py`) selon `shared/CONVENTIONS.md` :
   - statuts évidents : vide → `NON_FOURNI`, « ? » → `INCONNU` ;
   - conversion au type du schéma : dates, nombres, tension « 110/70 », choix ;
   - `A_REVISER` si la valeur est hors de sa plage plausible ou si la confiance est sous le seuil.
4. **Confiance finale** (`confiance.py`) : confiance du modèle × plausibilité × cohérence entre champs (dates,
   âge gestationnel…) × signal de réflexion. Une page qui a demandé beaucoup plus de réflexion qu'une page propre
   voit sa confiance baisser.
5. **Validation** par `shared/valider.py` avant de rendre le résultat.

Le seuil de question `seuil_question_suivi` vient de `shared/statuts.json` : **0,92**, fixé par la calibration de
`evaluation/`.

## Cache et coûts

Chaque lecture est mise en cache dans `extraction/cache/` (hors Git). La clé combine le sha256 de l'image, le type
de page, la version du prompt et de l'outil, le fournisseur, le modèle et le niveau d'effort. Une page déjà lue ne
coûte rien. Si la sortie est tronquée, la lecture est relancée à un effort plus bas (medium, puis low) ; chaque
essai est mis en cache. `CACHE_SEULEMENT = True` dans `client.py` interdit tout appel à l'API.

## Scripts (depuis la racine, venv activé)

| Script | Rôle |
|---|---|
| `index_donnees.py` | Index des images de `data/` : sha256, page, patiente, type de page, doublons, découpage dev / test |
| `essai.py` | Extrait et affiche une ou plusieurs pages (dev seulement), puis les valide |
| `lot.py` | Extraction d'un lot (48 pages de dev ; versions dégradées avec `--degradation`) |
| `degrader.py` | Six dégradations reproductibles des 48 pages de dev (flou, rotation, ombre, sombre, JPEG, combinaison) |
| `non_regression.py` | Repasse tout le cache dans la normalisation actuelle, sans appel API ; code 1 si une page devient invalide |
| `sorties.py` | Sorties détaillées par page avec les signaux de confiance (`sorties/`) |
| `rapport_robustesse.py` | Rapport sur les images dégradées (`rapports/robustesse_degradations.md`), en lisant le cache |

Clé API : `ANTHROPIC_API_KEY` dans `.env` ou dans l'environnement, jamais commitée. Sans clé :
`EXTRACTION_FOURNISSEUR=simule`.

## Résultats et limites

Les scores (pages propres et dégradées, calibration) sont dans [evaluation/README.md](../evaluation/README.md).
Sur les 48 pages propres de dev, les valeurs sont exactes à 100 % et les champs entièrement exacts à 98,84 %. Le
flou, la rotation et leur combinaison font nettement baisser la qualité. Ces deux dernières dégradations
provoquent quelques échecs du pipeline. Les pages 49 à 80 restent réservées à l'évaluation finale. L'écriture
arabe est transcrite telle quelle, mais elle n'a pas été évaluée.
