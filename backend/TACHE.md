# Tâche 4 – Serveur · dossier backend/ · branche backend
Points visés : hors ligne 15, liaison patiente et confidentialité 10.

## Mission
Que rien ne se perde jamais, même quand la connexion tombe, et que les visites soient bien reliées.

## Stack et prérequis
- FastAPI, uvicorn, python-multipart (envoi d'images), pydantic : voir backend/requirements.txt.
- SQLite via le module standard `sqlite3`, fichier `backend/stockage/firstbreath.db`.
- Images d'origine stockées dans `backend/stockage/images/` (jamais modifiées).
- Hash des images avec `hashlib` (sha256), identifiants avec `uuid4`.
- Validation de toute donnée avec `shared/valider.py`.
- backend/stockage/ n'est pas commité (.gitignore).
- Lancement depuis la racine : `uvicorn backend.main:app --reload --port 8000` (voir GUIDE_EQUIPE.md).

## Étapes
1. Toutes les routes de shared/CONTRAT.md, d'abord avec des réponses simulées (pour qu'Aloys se branche tôt).
2. Machine à états du cycle de vie (shared/statuts.json), avec les états d'échec ; chaque transition est historisée.
3. Brancher extract_page() de extraction/pipeline.py (sans la modifier).
4. /sync idempotent : un lot renvoyé deux fois ne crée aucun doublon ; rien n'est perdu si la connexion coupe.
5. Doublons : même hash d'image -> DOUBLON_SUSPECTE.
6. Liaison par N° de fiche : proposer les candidates, ne jamais créer de patiente automatiquement ;
   gérer « Aucune, créer » et « Je ne sais pas ».
7. Renumérisation : si un registre est rephotographié, renvoyer le dossier existant pour que la sage-femme choisisse quoi mettre à jour.
8. Image d'origine liée au dossier (date de capture, sage-femme, statut), accès limité selon le rôle.
9. Rejeter toute donnée qui ne passe pas shared/valider.py. Test final : couper la connexion en plein traitement.

## Terminé quand
Le parcours CAPTURE -> SYNCHRONISE fonctionne avec une coupure réseau simulée, sans perte ni doublon.

## Prompt Claude Code
```
Je travaille dans backend/ (branche backend). Lis CLAUDE.md, GUIDE_EQUIPE.md, backend/TACHE.md et tout le dossier shared/. Résume ma tâche en 10 lignes, puis attends mon accord. Ensuite réalise les étapes de backend/TACHE.md une par une avec FastAPI, en t'arrêtant après chacune pour que je teste. Respecte exactement les routes de shared/CONTRAT.md. Utilise extract_page() sans la modifier. Ne modifie que backend/. Je suis sous Windows avec PowerShell.
```
