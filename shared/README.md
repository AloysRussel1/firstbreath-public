# FirstBreath — shared

Référence commune à toute l'équipe. Elle ne change qu'avec l'accord de tous ; chaque partie du projet la lit
plutôt que de la recopier.

| Fichier | Contenu |
|---|---|
| `schema_champs.json` | Schéma des champs, déduit des sections du registre : 8 types de page, 245 champs typés avec libellés français et anglais, choix possibles et plages plausibles, dont les 9 visites de la grossesse |
| `statuts.json` | Statuts des champs, états du dossier et d'échec, types de page, champs interdits, `seuil_question_suivi` |
| `CONVENTIONS.md` | Règles de remplissage : quel statut pour quelle situation, formats, confiance, confidentialité |
| `CONTRAT.md` | Interface entre les parties : `extract_page()` et les routes de l'API |
| `valider.py` | Validateur commun des pages et des dossiers, utilisé par l'extraction, le backend et l'évaluation |
| `exemple_dossier.json` | Exemple de dossier valide |

**Statuts d'un champ** : `CONNU`, `INCONNU`, `NON_FOURNI`, `ILLISIBLE`, `NON_APPLICABLE`, `A_REVISER`. Le validateur
refuse toute clé hors du schéma et tout champ interdit (nom, prénom, nom du mari, CIN, téléphone, adresse).

**Seuil de question** : `seuil_question_suivi` vaut 0,92. Ce choix vient de la calibration du développement
(voir `evaluation/README.md`) ; il valait 0,75 auparavant.

```powershell
python shared/valider.py chemin/vers/fichier.json     # affiche VALIDE ou la liste des erreurs
```
