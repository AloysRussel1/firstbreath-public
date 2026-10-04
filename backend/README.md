# FirstBreath — backend

API FastAPI et stockage SQLite du centre de santé. Le backend reçoit les photos, lance la lecture (`extraction/`)
en tâche de fond et tient le cycle de vie de chaque dossier. Il gère aussi la liaison patiente, la
synchronisation avec le système de santé (simulé) et le tableau de bord anonymisé.

## Lancer

```powershell
# depuis la racine du dépôt
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.venv\Scripts\uvicorn.exe backend.main:app --port 8000          # documentation interactive : /docs
.venv\Scripts\python.exe -m pytest -q backend\tests              # 35 tests
```

| Variable | Rôle | Défaut |
|---|---|---|
| `EXTRACTION_FOURNISSEUR` | `anthropic` (lecture réelle, cache d'abord) ou `simule` (confiance 0 : tout devient question) | `anthropic` |
| `FIRSTBREATH_DATA_DIR` | Base SQLite et images d'origine | `backend/storage/` (hors Git) |
| `FIRSTBREATH_CORS_ORIGINS` | Origines autorisées pour l'interface | `localhost:5173`, `127.0.0.1:5173` |
| `FIRSTBREATH_MAX_UPLOAD_BYTES` | Taille maximale d'une photo | 10 Mo |
| `FIRSTBREATH_REQUIRED_FIELDS` | Champs obligatoires pour valider (tableau JSON) | `["identification.numero_fiche"]` |

Le seuil de question est lu dans `shared/statuts.json` (`seuil_question_suivi`, 0,92). Il peut être forcé avec
`FIRSTBREATH_CONFIDENCE_THRESHOLD`.

## Routes

En-têtes envoyés par l'interface : `X-Sage-Femme-Id` (identifiant professionnel) et `X-Role` (`SAGE_FEMME` ou
`SUPERVISEUR`).

| Route | Rôle |
|---|---|
| `GET /sante`, `GET /schema` | Santé du serveur ; schéma, visites, statuts, seuil et `fournisseur_extraction` (`simule` : aucune lecture réelle) |
| `POST /captures` | Photo, `session_id` et `page_no` → capture (idempotente) ; même image déjà envoyée → `DOUBLON_SUSPECTE` |
| `POST /captures/{id}/traiter` | Lance la lecture en tâche de fond → `EN_ATTENTE_IA` |
| `GET /captures/{id}/etat` | Progression, durée estimée, état final, dossier |
| `GET /captures/{id}` | Métadonnées : dossier, date de capture, sage-femme, état de traitement, sha256 |
| `GET /captures/{id}/image` | Image d'origine : la sage-femme voit les siennes, le superviseur toutes ; accès journalisés |
| `GET /dossiers` | Liste et états (filtrée par rôle) |
| `GET /dossiers/{id}`, `GET …/historique`, `GET …/validation` | Dossier, transitions et historique des champs, champs manquants |
| `PATCH /dossiers/{id}/champs` | Confirmer, corriger ou saisir un champ (historisé) |
| `POST /dossiers/{id}/confirmer` | « Tout confirmer » : uniquement les champs fiables |
| `POST /dossiers/{id}/validate` | → `VALIDE` si les champs obligatoires sont sûrs et qu'aucun champ douteux n'attend de réponse ; sinon `blocages` (`champs_obligatoires`, `questions`, `donnees_invalides`) |
| `POST /dossiers/{id}/renumerisation` | Nouvelle photo d'une page déjà saisie : seuls les champs choisis remplacent l'existant |
| `GET /patientes/correspondances?code=&numero_fiche=` | Candidates (jamais de liaison automatique) |
| `POST /dossiers/{id}/lier` | `{patiente_id, code}` \| `{choix: "nouvelle", code?}` \| `{choix: "inconnu"}` → `PATIENTE_LIEE` |
| `GET /patientes` | Patientes par code de liaison, avec l'historique de leurs visites |
| `POST /dossiers/{id}/enregistrer` | `VALIDE` ou `PATIENTE_LIEE` → `ENREGISTRE` |
| `POST /synchronisation` | `ENREGISTRE` ou `ECHEC_SYNCHRONISATION` → `SYNCHRONISE` (copie anonymisée vers le système central simulé). Avec `{simuler_panne: true}` → `ECHEC_SYNCHRONISATION` |
| `GET /tableau-de-bord?source=dossiers\|demo` | Agrégats sur les dossiers validés, ou sur le CSV synthétique des organisateurs (`demo`, signalé `synthetique`) ; parts dépistées et positives ; toute case de moins de 5 dossiers est masquée |
| `POST /dossiers/{id}/pages/{n}/retirer` | Retire une page d'une autre patiente (capture et image conservées) |
| `POST /captures/{id}/nouveau-registre` | Place une capture lue dans un nouveau registre, sans renvoyer la photo |
| `POST /sync`, `GET /sync/status` | Lot de captures faites hors ligne ; décompte par état |
| `POST /doublons/{id}/decision` | Décision sur un doublon suspecté |

## Cycle de vie

Transitions autorisées : `TRANSITIONS` dans [services.py](services.py). Une transition invalide renvoie 409. Chaque
transition est inscrite dans la table `transitions` et dans `historique_etats` du dossier.

```
CAPTURE → EN_ATTENTE_IA → TRAITE_IA | A_REVISER → VALIDE → PATIENTE_LIEE → ENREGISTRE → SYNCHRONISE
échecs : ECHEC_TRAITEMENT, REVISION_MANUELLE_REQUISE, DOUBLON_SUSPECTE, ECHEC_SYNCHRONISATION
```

- Une lecture interrompue par un redémarrage passe en `ECHEC_TRAITEMENT` au démarrage et peut être relancée.
- Une page ajoutée à un dossier déjà validé le renvoie en `A_REVISER`.
- Le système central est simulé par la table `systeme_central` : champs, statuts et code de liaison, sans image
  ni identifiant de la sage-femme.

## Choix techniques

- **SQLite en transactions `BEGIN IMMEDIATE`** : plusieurs lectures en parallèle ne s'écrasent pas. Un test de
  concurrence le vérifie.
- **Captures idempotentes**, avec la clé sage-femme + session + page + empreinte de l'image : un renvoi après une
  coupure ne crée rien.
- **Toute donnée extraite passe par `shared/valider.py`.** Les valeurs qui ressemblent à un téléphone ou à une
  CIN sont écartées, et les clés interdites n'existent pas dans le schéma.
- **Images d'origine** stockées telles quelles dans un dossier privé, servies avec `Cache-Control: no-store`.

## Tests

| Fichier | Ce qui est vérifié |
|---|---|
| `test_services.py` | Idempotence et doublon ; saisie manuelle et historique ; identifiants interdits refusés ; synchronisation hors ligne |
| `test_traitement_asynchrone.py` | Lecture en fond, progression, relance après échec, concurrence, reprise après redémarrage |
| `test_captures_et_images.py` | Métadonnées, accès à l'image selon le rôle, filtrage des champs non valides |
| `test_interface_api.py` | `/schema` et seuil lu dans `statuts.json` ; « tout confirmer » limité aux champs fiables |
| `test_liaison_et_dossiers.py` | Code de liaison, candidates sans liaison automatique, listes par rôle, renumérisation |
| `test_tableau_de_bord.py` | Dossiers validés seulement, cases de moins de 5 dossiers masquées ; source de démonstration (CSV) |
| `test_validation.py` | Blocages de validation (questions restantes) ; mode de lecture exposé par `/schema` |
| `test_autre_patiente.py` | N° du registre non écrasé ; page retirée ; capture placée dans un nouveau registre |
| `test_cycle_de_vie.py` | Cycle complet jusqu'à `SYNCHRONISE`, avec panne et reprise ; copie anonymisée ; page ajoutée après validation ; code choisi par la sage-femme |
| `test_bout_en_bout.py` | Parcours HTTP complet |

`conftest.py` force le fournisseur simulé, une base et un cache temporaires : aucun test n'appelle l'API.
