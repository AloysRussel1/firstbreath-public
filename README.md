# FirstBreath

Agent conversationnel qui transforme la photo d'un registre maternel papier en dossier numérique structuré.
Il fonctionne d'abord hors ligne, la sage-femme vérifie chaque doute, et les visites d'une même femme sont
reliées entre elles. Défi DayOne, CodeML 2026.

Le registre papier reste la référence : l'application s'y greffe sans changer la pratique de la sage-femme.
Elle lit la page, pose une question seulement quand elle doute, et la sage-femme tranche toujours.

## Données

Ce dépôt ne contient **pas** les données du défi. Le registre synthétique (pages photographiées, PDF et CSV de
référence) est fourni par les organisateurs du défi DayOne (CodeML 2026) ; il n'est pas redistribué ici. Pour
utiliser les vraies lectures ou relancer l'évaluation, placer ces fichiers à la racine du dépôt :

```
data/
├── Paper Registry/                      images et PDF du registre synthétique (dossiers_specimen_10_patientes-*.png, …)
└── maternal_registry_synthetic.csv      200 lignes synthétiques (source « Données de démonstration » du tableau de bord)
```

Sans `data/`, l'application, le mode simulé (`EXTRACTION_FOURNISSEUR=simule`) et les tests fonctionnent ; les tests
qui lisent ces fichiers sont ignorés, et la source « Données de démonstration » du tableau de bord est indisponible.
Aucune donnée réelle de patiente n'est utilisée : les photos `1-*.jpg`, qui semblent réelles, n'ont jamais été
envoyées à l'API.

## Installation

**Prérequis** : Python 3.12 ou plus, Node 20 ou plus, Git.

**Données** : le registre synthétique des organisateurs va dans `data/` (hors Git) :
`data/Paper Registry/` et `data/maternal_registry_synthetic.csv`. Sans `data/`, l'application et les tests
fonctionnent ; les tests qui lisent ces fichiers sont ignorés.

### 1. Backend et pipeline d'extraction (depuis la racine du dépôt)

Windows (PowerShell). Le lanceur `py` crée un environnement standard ; le préfixe `.\` est obligatoire en
PowerShell.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r evaluation\requirements.txt
$env:EXTRACTION_FOURNISSEUR = "simule"         # sans clé d'API (voir plus bas)
.\.venv\Scripts\uvicorn.exe backend.main:app --port 8000
```

macOS / Linux :

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt -r evaluation/requirements.txt
EXTRACTION_FOURNISSEUR=simule .venv/bin/uvicorn backend.main:app --port 8000
```

Vérification : `http://127.0.0.1:8000/sante` doit répondre `{"ok":true,"service":"firstbreath-api"}`, et la
documentation de l'API est sur `http://127.0.0.1:8000/docs`.

### 2. Interface (autre terminal)

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173
```

Ouvrir `http://localhost:5173`, choisir « Commencer », un identifiant (par exemple `sf_01`) et le rôle
Sage-femme.

### 3. Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q backend\tests                                  # 35 tests
.\.venv\Scripts\python.exe -B -m unittest discover -s evaluation -p "test_*.py"         # 42 tests
cd frontend; npm run lint; npm run build
```

Sous macOS / Linux, remplacer `.\.venv\Scripts\python.exe` par `.venv/bin/python`. Les tests du backend forcent
le fournisseur simulé : ils ne font jamais d'appel payant.

### Modes de lecture

- **Sans clé (jury, essai)** : `EXTRACTION_FOURNISSEUR=simule`. Aucune lecture réelle : chaque champ arrive vide,
  avec une confiance de 0, et devient une question ; l'interface affiche l'avis « Mode sans lecture ». Le parcours
  complet reste jouable : saisie, validation, liaison, synchronisation, tableau de bord.
- **Lecture réelle** : `ANTHROPIC_API_KEY` dans `.env` ou dans l'environnement (jamais commité), avec
  `EXTRACTION_FOURNISSEUR=anthropic` (valeur par défaut). Les pages déjà lues sont servies par le cache local
  `extraction/cache/` (hors Git), sans appel ni coût.

### Si le port 8000 est occupé

```powershell
$env:FIRSTBREATH_CORS_ORIGINS = "http://localhost:5173"
.\.venv\Scripts\uvicorn.exe backend.main:app --port 8001
# dans le terminal de l'interface :
$env:VITE_API_BASE_URL = "http://127.0.0.1:8001"; npm run dev
```

Note Windows : si le contrôle intelligent des applications (Smart App Control) bloque une bibliothèque compilée
fraîchement téléchargée (par exemple `scikit-learn`, utilisé seulement par les tests de calibration), les autres
tests restent valables ; débloquer le fichier ou relancer depuis un dossier de confiance.

## Architecture et choix de conception

```
Téléphone : frontend/ (React)               Serveur du centre : backend/ (FastAPI + SQLite)
  conversation, file d'attente      HTTP      captures, dossiers, liaison, cycle de vie
  coffre chiffré (IndexedDB, AES-GCM) <----->  image d'origine privée, accès selon le rôle
  contrôle de qualité de la photo              extraction/ : lecture de la page par Claude
                                               « système de santé central » simulé (synchronisation)
                 shared/ : schéma des champs, statuts, contrat, validateur commun
```

| Dossier | Rôle | Documentation |
|---|---|---|
| `shared/` | Schéma des 245 champs, statuts, contrat d'interface, validateur | [shared/README.md](shared/README.md) |
| `extraction/` | Photo → objet structuré avec statut et confiance par champ | [extraction/README.md](extraction/README.md) |
| `backend/` | API, cycle de vie, liaison patiente, synchronisation, tableau de bord | [backend/README.md](backend/README.md) |
| `frontend/` | Application mobile : conversation, dossiers, tableau de bord, réglages | [frontend/README.md](frontend/README.md) |
| `evaluation/` | Vérité terrain, scores, robustesse, calibration du seuil | [evaluation/README.md](evaluation/README.md) |
| `docs/` | [Conformité aux consignes](docs/CONFORMITE.md) | |

Choix principaux :

- **Partir du schéma, pas de l'OCR.** Le modèle remplit un outil généré depuis `shared/schema_champs.json`. Le
  code normalise ensuite les valeurs et fixe les statuts selon `shared/CONVENTIONS.md`.
- **Une conversation plutôt qu'un formulaire.** Une page compte jusqu'à 160 champs. La sage-femme ne voit que les
  doutes, une question à la fois, avec quatre réponses de même poids : Confirmer, Corriger, Vide sur le papier,
  Reprendre la photo. Le détail complet est à un geste ; sur grand écran, il s'affiche à côté du fil.
- **Statuts neutres, aucun triage.** Ni vert, ni jaune, ni rouge : la forme de l'icône et le libellé distinguent
  les statuts. Il n'y a ni diagnostic ni recommandation.
- **Contre le biais d'automatisation.** Un doute ne se confirme jamais en bloc. La renumérisation garde l'existant
  par défaut. La liaison n'est jamais automatique.
- **Hors ligne d'abord.** Photos, conversation et listes sont stockées chiffrées sur l'appareil. Les envois au
  serveur sont idempotents : un renvoi ne crée pas de doublon.

## Schéma des champs et statuts

- **8 types de page**, calqués sur le livret : identification, antécédents, grossesse actuelle (avec 9 visites),
  accouchement, post-partum précoce et tardif pour la mère et pour le nouveau-né. Au total, **245 champs** typés
  (date, entier, décimal, tension, choix, liste…) avec des plages plausibles.
- **6 statuts par champ** :

  | Statut | Signification |
  |---|---|
  | `CONNU` | Valeur lue |
  | `INCONNU` | « ? » écrit sur le registre |
  | `NON_FOURNI` | Laissé vide |
  | `ILLISIBLE` | Écriture impossible à lire |
  | `NON_APPLICABLE` | Sans objet |
  | `A_REVISER` | Lecture douteuse |

  Jamais de « N/A » : on dit toujours pourquoi une valeur manque.
- **Question de suivi** pour tout champ `A_REVISER` ou `ILLISIBLE`, ou `CONNU` avec une confiance sous
  `seuil_question_suivi`. Ce seuil vaut **0,92** depuis la calibration (voir l'évaluation ci-dessous) ; il est lu
  dans `shared/statuts.json` par l'extraction, le backend et l'interface.
- Les champs interdits (nom, prénom, nom du mari, CIN, téléphone, adresse) n'existent pas dans le schéma, sont
  refusés par le validateur et filtrés par le backend.

## Cycle de vie des enregistrements

Un registre photographié en une session forme un seul dossier. Chaque transition est historisée (date, acteur,
raison) et visible dans la vue d'un dossier.

| État | Comment il est atteint (dans l'application) |
|---|---|
| `CAPTURE` | La photo est reçue par le serveur |
| `EN_ATTENTE_IA` | La lecture est lancée (« Je lis la page… ») |
| `TRAITE_IA` | Lecture terminée, aucun champ douteux |
| `A_REVISER` | Lecture terminée avec des doutes, ou nouvelle page ajoutée à un dossier déjà validé |
| `VALIDE` | « Valider le dossier » une fois les champs obligatoires sûrs et toutes les questions répondues. Sinon l'agent dit ce qui bloque (« Il reste 2 questions », « Une comparaison est en attente »…) avec un bouton pour y aller |
| `PATIENTE_LIEE` | Choix explicite d'une patiente, ou création avec un code |
| `ENREGISTRE` | Automatique après la décision de liaison (« Je ne sais pas » compris) : dossier inscrit dans le registre numérique du centre |
| `SYNCHRONISE` | Copie anonymisée (sans image ni identifiant direct) transmise au système de santé central, simulé par une table du serveur |
| `ECHEC_TRAITEMENT` | Lecture impossible, ou serveur redémarré pendant une lecture. Relancer, reprendre la photo ou saisir à la main |
| `ECHEC_SYNCHRONISATION` | Système central injoignable (panne simulée dans Réglages). Nouvelle tentative automatique au retour de la connexion, ou « Synchroniser maintenant » |
| `DOUBLON_SUSPECTE` | La même image est envoyée une seconde fois. L'application propose d'ouvrir le dossier existant |
| `REVISION_MANUELLE_REQUISE` | Saisie manuelle après un échec, ou sortie d'extraction non conforme au contrat |

Côté téléphone, chaque photo a aussi un état local : contrôle de qualité, « En attente de traitement IA (hors
ligne) », envoi, puis « En attente de traitement IA (reçue) ». Les 12 états du serveur sont atteints par le
parcours automatisé décrit dans [docs/CONFORMITE.md](docs/CONFORMITE.md).

## Mode hors ligne et synchronisation

- **Sans réseau** (réel, ou « Simuler hors ligne »), la photo est chiffrée dans IndexedDB avant d'entrer dans la
  file : clé AES-GCM-256 non extractible, IV aléatoire à chaque écriture. Un journal des photos en file survit à un
  rechargement immédiat.
- **Au retour de la connexion**, la file repart seule : envoi, lecture, suivi. Une coupure en pleine lecture ne
  perd rien : le serveur continue et le suivi reprend au retour. Une lecture interrompue par un redémarrage du
  serveur passe en `ECHEC_TRAITEMENT` et peut être relancée.
- **Synchronisation avec le système de santé** : idempotente, une ligne par dossier. Elle est tentée après
  l'enregistrement, au retour de la connexion et depuis Réglages ou la vue du dossier.

## Liaison patiente et confidentialité

- **Nouvelle patiente** : l'application génère un code court et aléatoire (`XXX-XXX`, sans 0/O ni 1/I) que la
  sage-femme recopie sur le registre. Si le registre porte déjà un code qu'elle a écrit, elle peut créer la
  patiente avec ce code.
- **Visite suivante** : candidates par code et par N° de fiche, présentées en [Patiente 1] [Patiente 2] …
  [Aucune, créer] [Je ne sais pas], avec le code, le N° de fiche et le nombre de visites. Rien n'est jamais lié ni
  créé automatiquement.
- **Identifiants internes** : UUID aléatoires, jamais dérivés de données personnelles. Aucun nom, CIN, téléphone
  ni adresse n'est stocké ou affiché ; le profil est un identifiant professionnel.
- **Image d'origine** : conservée sans modification, liée au dossier, à la date de capture, à la sage-femme et à
  l'état de traitement. Une sage-femme voit ses propres photos, un superviseur les voit toutes ; chaque accès est
  journalisé.
- **Aucune donnée réelle** n'est envoyée à un service tiers : seules les pages synthétiques sont lues par l'API
  Anthropic.

## Évaluation de l'extraction (résultats)

Méthode détaillée et tous les chiffres : [evaluation/README.md](evaluation/README.md). La vérité terrain est
construite à partir du PDF synthétique ; les comparaisons utilisent des tolérances fixées à l'avance.

### Score officiel sur le jeu de test (patientes 7 à 10, jamais vues pendant le développement)

L'évaluation a été lancée une seule fois, modèle et seuil gelés, sur 32 pages (49 à 80, doublons exclus) ; elle a
coûté 1,61 $ et 623 s. La référence du test est partielle : 619 champs annotés sur 980.

| Mesure | Résultat |
|---|---:|
| Valeurs exactes | **98,92 %** (547/553) |
| Statuts exacts | 54,28 % (336/619) |
| Champs entièrement exacts (valeur et statut) | 53,63 % (332/619) |
| Valeurs fausses sans alerte au seuil 0,92 | **0,65 %** (4/619) |
| Questions par page | 11,4 en moyenne ; médiane 3,5 ; jusqu'à 156 sur une page de grossesse |

Les valeurs lues restent aussi justes qu'en développement. Les statuts « exacts » baissent parce que le seuil
prudent de 0,92 envoie en question 224 champs que la référence donne « connus » : ce sont des questions de plus,
pas des erreurs silencieuses.

### Développement (patientes 1 à 6, pages 1 à 48) et robustesse aux photos dégradées

Ces scores ont été mesurés avec l'ancien seuil de 0,75.

| Images (48 pages) | Valeurs exactes | Champs entièrement exacts (valeur et statut) |
|---|---:|---:|
| Propres | 100,00 % (1 028/1 028) | 98,84 % (1 453/1 470) |
| Ombre | 99,90 % | 98,91 % |
| Sous-exposition | 99,90 % | 99,32 % |
| JPEG compressé | 99,03 % | 98,23 % |
| Flou | 85,41 % | 68,30 % |
| Rotation (4 échecs de pipeline) | 62,45 % | 54,22 % |
| Combinaison (2 échecs) | 67,22 % | 52,38 % |

### Calibration et seuil de question

La calibration utilise une régression isotone, apprise sur les patientes 1 à 4 et vérifiée sur les patientes 5
et 6. L'erreur de calibration (ECE) passe de 11,76 % à 0,76 %.

Le seuil retenu est une confiance brute d'au moins **0,92**. En vérification, il fait réviser 62,7 % des champs et
laisse **0 erreur observée sur 1 280 champs non révisés**. Il est appliqué dans `shared/statuts.json` ; les
figures sont dans `evaluation/figures/`.

## Limites connues

- **Écriture arabe** : l'extraction n'a pas été mesurée sur de l'arabe, faute de page arabe disponible dans le
  spécimen. L'interface affiche correctement l'arabe (police Noto Naskh Arabic embarquée, de droite à gauche), et
  le prompt demande de transcrire tel quel.
- **Vraies photos** : les photos `1-*.jpg` n'ont jamais été envoyées à l'API, par prudence, car elles semblent
  provenir d'un vrai registre. Aucune mesure n'existe donc sur de vraies photos.
- **Charge de révision** : le seuil de 0,92 ne laisse passer aucune erreur sur le développement, mais il pose
  beaucoup de questions sur les pages difficiles : jusqu'à 121 sur une page de grossesse en développement, et
  156 sur le jeu de test (65 par page de grossesse en moyenne). Piste : une vérification
  par section (confirmer une section entière après l'avoir relue), ou un seuil propre à chaque type de champ.
- **Raison du doute** : elle est déduite par l'interface à partir du statut et de la confiance (« lecture
  incertaine », « illisible »…). L'extraction ne transmet pas la raison précise par champ.
- **Photos inclinées** : il n'y a pas de redressement automatique. Le contrôle sur l'appareil signale le flou
  et le manque de lumière, pas l'inclinaison.
- **Clavier** : le maintien de la zone de saisie au-dessus du clavier virtuel n'a pas été testé sur un vrai
  téléphone ; il a été vérifié dans un navigateur de bureau.
- **Authentification** : il n'y en a pas de réelle. Le rôle est déclaré dans le profil et envoyé dans un
  en-tête HTTP. La clé du coffre chiffré vit dans le navigateur.
- **Hépatite** : le formulaire papier contient l'hépatite B (Ag HBs), et non l'hépatite C demandée par les
  consignes. Le schéma prévoit les deux champs, mais l'hépatite C est presque toujours absente du papier ; le
  tableau de bord ne l'illustre vraiment qu'avec les données de démonstration (CSV des organisateurs).
- **WhatsApp** : pas de connexion à un vrai bac à sable WhatsApp Business. Le prototype est une application web
  de type WhatsApp.
- **Données** : synthétiques. Six patientes en développement, quatre en test. La référence attend une relecture
  humaine indépendante.
- **Réseau** : la liaison, le tableau de bord, la photo d'origine et la renumérisation demandent une connexion.
  Le système de santé central est simulé par le serveur.
- **Doublons** : une même image envoyée deux fois est un doublon suspecté. Une renumérisation suppose donc une
  nouvelle photo.

## Outils, sources et modèles utilisés

- **Modèles Claude** (SDK `anthropic`) :

  | Modèle | Usage |
  |---|---|
  | `claude-sonnet-5` | Lecture des pages, sortie structurée par appel d'outil |
  | `claude-haiku-4-5` | Détection du type de page quand il est inconnu |
  | `claude-opus-5-5` | Assistant de développement (Claude Code) pour l'interface, le backend, les tests et la documentation ; il n'intervient pas dans l'extraction |

- **Logiciels** :

  | Partie | Outils |
  |---|---|
  | Backend | Python, FastAPI, SQLite, Pillow |
  | Évaluation | scikit-learn, RapidFuzz, PyMuPDF, pdftotext |
  | Interface | React 19, Vite, Dexie (IndexedDB), Web Crypto (AES-GCM) ; polices DM Sans, Playfair Display et Noto Naskh Arabic embarquées (OFL) |
  | Tests | pytest, unittest ; Playwright avec Microsoft Edge pour les parcours de bout en bout |

- **Données** : registre synthétique fourni par les organisateurs du défi DayOne (`data/`, jamais modifié).

## Équipe

Équipe FirstBreath, CodeML 2026. Les contributions de chacun sont visibles dans l'historique Git.
