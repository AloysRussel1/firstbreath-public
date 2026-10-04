# FirstBreath – Guide de l'équipe (à lire en premier)

## Le projet en 5 lignes
Une sage-femme photographie les pages d'un registre maternel papier dans un chat type WhatsApp.
L'IA lit la page et remplit un dossier numérique : pour chaque champ, une valeur, un statut et une confiance.
Quand elle doute, elle le dit et pose la question ; la sage-femme confirme ou corrige.
Tout marche sans internet (stockage chiffré, file d'attente, synchronisation au retour du réseau).
Les visites d'une même femme sont reliées par le N° de fiche ; la sage-femme décide des correspondances.

Grille : extraction 30, incertitude 20, vérification 20, hors ligne 15, liaison + confidentialité 10, code + doc 5.
Jamais stockés : nom, prénom, nom du mari, CIN, téléphone, adresse.
Hors périmètre : diagnostic, prédiction de risque, triage.

## Qui fait quoi
| Tâche | Dossier | Branche | Guide |
|---|---|---|---|
| 1 – Appli de chat (Aloys) | frontend/ | front | frontend/TACHE.md |
| 2 – Lecteur IA | extraction/ | extraction | extraction/TACHE.md |
| 3 – Correcteur | evaluation/ | eval | evaluation/TACHE.md |
| 4 – Serveur | backend/ | backend | backend/TACHE.md |

## Démarrer (une seule fois)
    git clone <URL du dépôt>
    cd firstbreath
    git checkout -b <ta-branche>
1. Copier le contenu du ZIP DayOne dans firstbreath/data/ (jamais modifié, jamais commité).
2. Lire dans l'ordre : ce guide, shared/CONVENTIONS.md, puis le TACHE.md de ton dossier.
3. Vérifier : `python shared/valider.py shared/exemple_dossier.json` doit afficher VALIDE.

## Prérequis et lancement
À installer : Git, Python 3.12 recommandé, Node 20+.
Si une bibliothèque refuse de s'installer avec Python 3.14, créer le venv en 3.12 (`py -3.12 -m venv .venv`).

Environnement virtuel Python, une seule fois, à la racine de firstbreath/ (PowerShell) :
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r backend/requirements.txt -r extraction/requirements.txt -r evaluation/requirements.txt
Si PowerShell bloque Activate.ps1 : `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Clés et configuration : copier `.env.example` (à la racine) en `.env`, puis le remplir.
    Copy-Item .env.example .env
    ANTHROPIC_API_KEY=
    VITE_API_URL=http://localhost:8000

Ports : backend sur 8000, frontend sur 5173.

Lancer le backend DEPUIS LA RACINE (pour que shared/ et extraction/ soient importables) :
    .venv\Scripts\Activate.ps1
    uvicorn backend.main:app --reload --port 8000
Lancer le frontend (dans un second terminal) :
    cd frontend
    npm install
    npm run dev

## Règles anti-conflits
1. Tu ne modifies QUE ton dossier.
2. shared/ et le README racine : personne n'y touche seul. On en parle, Aloys modifie.
3. Ta documentation va dans le README.md de ton dossier ; Aloys assemble le README final.
4. Tes dépendances vont dans ton dossier (requirements.txt ou package.json).
5. Clés d'API dans .env uniquement. Jamais de `git push --force`.

## Cycle Git
Pendant le travail, souvent :
    git add .
    git commit -m "mon-dossier : ce que j'ai fait"
    git push origin <ta-branche>
Toutes les 2 h, au point d'équipe :
    git checkout main
    git pull origin main
    git merge <ta-branche>
    git push origin main
    git checkout <ta-branche>
    git merge main
Conflit ? On s'arrête et on prévient le groupe.

## Utiliser Claude Code
Ouvrir le dossier firstbreath dans VS Code, ouvrir le panneau Claude Code, coller le prompt de ton TACHE.md.
CLAUDE.md est lu automatiquement. Avancer une étape à la fois, tester, commiter.

## Jalons
- H4 : première vraie extract_page() livrée (T2), évaluée (T3) et branchée (T4).
- H7 : une photo traverse toute l'appli.
- H13 : confiance calculée, hors ligne et liaison fonctionnels.
- H20 : gel des fonctionnalités -> corrections, README, vidéo.
- H23 : remise Devpost, UN SEUL prix (DayOne), même nom d'équipe et mêmes membres que sur HxBuddy.

## Point d'équipe (toutes les 2 h, 5 min)
Chacun répond : qu'est-ce que j'ai fini ? Qu'est-ce que je fais ensuite ? Qu'est-ce qui me bloque ?
