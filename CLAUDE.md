# FirstBreath – Contexte du projet pour Claude Code

## Le projet
Hackathon CodeML 2026 (24 h), défi DayOne – The Offline Midwife. Équipe de 4.
Agent conversationnel de type WhatsApp (simulé) : une sage-femme photographie les pages d'un
registre maternel papier ; l'IA extrait des données structurées avec un statut et une confiance
par champ ; la sage-femme confirme, corrige ou reprend la photo ; tout fonctionne hors ligne
(stockage local chiffré, file d'attente, synchronisation) ; les visites d'une même femme sont
reliées par le N° de fiche, la sage-femme tranche les correspondances.

Grille (100 pts) : extraction 30, incertitude 20, flux de vérification 20, hors ligne 15,
liaison patiente et confidentialité 10, code et documentation 5.
Hors périmètre : diagnostic, prédiction de risque, triage, recommandations cliniques.

## Source unique de vérité – à lire AVANT de coder
- `shared/CONVENTIONS.md` : formats des valeurs, choix des statuts, confiance, confidentialité.
- `shared/schema_champs.json` : les 117 champs (clés exactes, types, choix, plages plausibles).
- `shared/statuts.json` : statuts de champ, états du cycle de vie, types de page, champs interdits.
- `shared/CONTRAT.md` : interface `extract_page()` et routes de l'API.
- `shared/exemple_dossier.json` : dossier d'exemple à utiliser comme donnée simulée.
- `shared/valider.py` : validateur. Toute donnée produite doit passer
  `python shared/valider.py fichier.json`.
N'invente jamais de clé de champ, de statut ou d'état absent de ces fichiers.

## Organisation et règles anti-conflits
| Dossier | Responsable | Branche |
|---|---|---|
| frontend/ | Aloys (chat, vérification, stockage local chiffré, file hors ligne côté client) | front |
| extraction/ | Coéquipier 2 (pipeline IA, extract_page) | extraction |
| evaluation/ | Coéquipier 3 (vérité terrain, scores, calibration) | eval |
| backend/ | Coéquipier 4 (API FastAPI, états, sync, liaison, doublons) | backend |

1. Ne modifie QUE les fichiers du dossier de la personne qui travaille avec toi.
2. Ne modifie JAMAIS `shared/` ni le README racine. Si un changement y semble nécessaire,
   arrête-toi et propose-le en texte pour que l'équipe le valide.
3. Ne modifie JAMAIS `data/` (images et fichiers de référence en lecture seule).
4. Chaque dossier a son propre `requirements.txt` ou `package.json` et son propre `README.md`.
5. Clés d'API uniquement dans `.env` (jamais dans le code, jamais commitées).
6. Petits commits fréquents avec un message clair, sur la branche de la personne.
   Ne fais jamais `git push --force`.

## Contraintes non négociables
- Jamais stocker ni afficher : nom, prénom, nom du mari, CIN, téléphone, adresse.
- Identifiants internes : uuid aléatoires, jamais dérivés d'informations personnelles.
- Stockage local sur l'appareil chiffré (IndexedDB + Web Crypto AES-GCM).
- Ne jamais créer automatiquement une patiente si une correspondance est plausible :
  proposer [Patiente 1] [Patiente 2] [Aucune, créer] [Je ne sais pas].
- L'agent exprime toujours son doute (statut A_REVISER, ILLISIBLE…) au lieu de deviner.
- Aucun enregistrement perdu quand la connexion tombe et revient.

## Données disponibles (dans data/)
- `Paper Registry/dossiers_specimen_10_patientes.pdf` : 80 pages = 10 patientes x 8 pages,
  avec couche texte (vérité terrain via PyMuPDF ; les cases cochées ne sont pas dans le texte).
- `Paper Registry/*.png` : pages du spécimen, nombreux doublons identiques (dédupliquer par hash).
- `Paper Registry/1-*.jpg` : 5 vraies photos dégradées d'un vrai registre.
- `maternal_registry_synthetic.csv` : 200 lignes synthétiques, non reliées aux images.

## Environnement
Windows, PowerShell. Git Bash disponible dans C:\Program Files\Git\bin\bash.exe.
Frontend : React + Vite (ESLint). Backend : Python, FastAPI.
Détails et commandes de lancement : GUIDE_EQUIPE.md (« Prérequis et lancement ») et chaque TACHE.md.
- Outils : Git, Python 3.12 recommandé (venv `.venv` à la racine), Node 20+. Clés dans `.env` (copie de `.env.example`).
- Ports : backend 8000 (`uvicorn backend.main:app --reload --port 8000`, lancé depuis la racine), frontend 5173.
- frontend/ : React 19 + Vite, dexie (IndexedDB), Web Crypto natif (AES-GCM), `crypto.randomUUID()`,
  CSS simple, URL de l'API dans `import.meta.env.VITE_API_URL`, tous les appels dans `src/api.js`.
- backend/ : FastAPI, uvicorn, python-multipart, pydantic ; SQLite (`sqlite3`, `backend/stockage/firstbreath.db`),
  images dans `backend/stockage/images/`, sha256 via `hashlib`, `uuid4`, validation par `shared/valider.py`.
- extraction/ : SDK `anthropic`, modèle `claude-sonnet-5` par défaut, `claude-opus-5-5` pour les pages difficiles ;
  sortie JSON par tool use ; python-dotenv, Pillow, hashlib. Uniquement des données synthétiques envoyées à l'API.
- evaluation/ : PyMuPDF (couche texte du PDF), pandas, matplotlib, scikit-learn (calibration_curve), rapidfuzz.
- Dépendances Python par dossier : `backend/`, `extraction/`, `evaluation/` ont chacun leur `requirements.txt`.

## Façon de travailler
- Commence par une version simple qui marche de bout en bout, puis améliore.
- Utilise les données simulées de `shared/` tant que les autres briques ne sont pas prêtes.
- Explique brièvement ce que tu as fait et comment le tester après chaque étape.
- Documente les choix de conception et les limites dans le README du dossier.
