# Conformité aux consignes du défi DayOne

Ce tableau couvre les sections 3, 5, 6, 7, 8 et 9 de `data/consignes-fr-en.pdf`. Chaque exigence a été vérifiée
dans le code et en jouant le parcours dans le navigateur, sauf mention contraire.

**Comment c'est vérifié**

- **Parcours automatisés** : Playwright avec Microsoft Edge, en téléphone de 390 px. Le serveur est lancé en mode
  « cache seulement », donc sans aucun appel à l'API. Les pages utilisées sont les originaux 1, 9, 17 et 25 des
  pages 1 à 48.
- **États du cycle de vie** : les 12 états ont été observés dans un même parcours.
- **Tests** : 35 tests backend (`pytest`) et 42 tests d'évaluation (`unittest`).

**Bilan : 34 exigences faites, 1 partielle, 1 manquante** (le bac à sable WhatsApp, exclu de la demande).

## Section 5 : tâches demandées

| # | Exigence | État | Où | Comment vérifier dans l'application |
|---|---|---|---|---|
| 5.1 | Schéma de champs et statuts définis à partir des sections du registre | Fait | `shared/schema_champs.json` (8 types de page, 245 champs), `shared/statuts.json`, `shared/CONVENTIONS.md` | Photographier une page, puis « Voir le détail » : sections du registre, 6 statuts distincts par leur icône. `GET /schema` |
| 5.2a | Pipeline photo → objet structuré, statut et confiance par champ | Fait | `extraction/pipeline.py`, `normalisation.py`, `confiance.py` | Page 9 : « N° de la fiche, lu 2026-A16-002 », statut « À vérifier », confiance 60 % |
| 5.2b | Évalué sur un jeu de test, résultats documentés | Fait | `evaluation/README.md` (section « Score officiel »), `evaluation/score_test_final.json`, résumé dans `README.md` | Jeu de test (patientes 7 à 10, lancé une seule fois, modèle gelé) : valeurs exactes 98,92 %, valeurs fausses sans alerte 0,65 % au seuil 0,92 ; développement, robustesse et calibration documentés |
| 5.3a | Présenter les données extraites | Fait | `pages/Conversation.jsx`, `components/DetailDossier.jsx`, `SectionsDossier.jsx` | Résumé de chaque page, « Voir le détail » ; panneau latéral au-delà de 1100 px |
| 5.3b | Confirmer / Corriger / Reprendre la photo | Fait | `components/CarteQuestion.jsx` | Quatre réponses de même poids sur chaque question (avec « Vide sur le papier ») |
| 5.3c | Questions de suivi pour les champs illisibles ou douteux | Fait | `etat/conversation.jsx` (une question à la fois), seuil 0,92 | `ILLISIBLE`, `A_REVISER` ou confiance sous 0,92 : « Question 1 sur N » |
| 5.3d | Saisie manuelle complète si l'IA est indisponible | Fait (corrigé) | `choisir('saisie:…')`, `DetailDossier.jsx` (fusion page serveur et champs vides) | Lecture impossible : [Saisir à la main], type de page, chaque ligne se saisit, puis [Valider le dossier]. Avant correction, seul le premier champ restait saisissable |
| 5.3e | L'agent dit quand il doute | Fait | `lib/format.js` (`raisonDoute`), textes `doute.*` | « Lecture incertaine… (confiance 60 %) : vérifiez sur le registre. » |
| 5.4a | Stockage local chiffré | Fait | `lib/coffre.js` (AES-GCM-256, clé non extractible, IV aléatoire) | Photos, conversation et listes en IndexedDB, illisibles sans la clé |
| 5.4b | File « En attente de traitement IA » | Fait | `etat/conversation.jsx` (états `EN_FILE`, `A_TRAITER`), journal des photos | « Simuler hors ligne », photo : « En attente de traitement IA (hors ligne) », conservée après rechargement |
| 5.4c | Envoi, traitement et synchronisation au retour de la connexion | Fait | Reprise automatique de la file ; `POST /synchronisation` au retour de la connexion | « Rétablir la connexion » : envoi, lecture et question, sans geste |
| 5.4d | Coupure en plein traitement | Fait | Suivi `/etat` relancé au retour ; `reprendre_interrompus()` au redémarrage du serveur | Pendant « Je lis la page… », couper puis rétablir : le résultat arrive (parcours R3) |
| 5.5a | États CAPTURE, EN_ATTENTE_IA, TRAITE_IA, A_REVISER, VALIDE, PATIENTE_LIEE | Fait | `backend/services.py` (`TRANSITIONS`) | Historique d'un dossier (vue dossier, « Historique des états ») |
| 5.5b | ENREGISTRE puis SYNCHRONISE | Fait (ajouté) | `enregistrer()`, `synchroniser()`, table `systeme_central` (système de santé simulé) | Après la liaison : « Dossier enregistré… », puis « dossier synchronisé ». Onglet Dossiers : état « Synchronisé » |
| 5.5c | Les 4 états d'échec | Fait | `ECHEC_TRAITEMENT` (lecture impossible ou redémarrage), `ECHEC_SYNCHRONISATION` (panne simulée), `DOUBLON_SUSPECTE` (même image), `REVISION_MANUELLE_REQUISE` (saisie après échec) | Réglages, « Simuler une panne du système de santé » : « Échec de synchronisation », puis reprise ; renvoyer une même photo : doublon |
| 5.6a | Code attribué par la sage-femme et inscrit sur le registre | Fait | `generer_code()` (aléatoire, sans 0/O ni 1/I), création avec le code de la sage-femme (`choix: nouvelle, code`) | « Créer une patiente » : code à recopier, [J'ai recopié le code]. Ou bien [Créer la patiente avec le code ABC-234] |
| 5.6b | Correspondances possibles, jamais de création automatique | Fait | `match_patients()` (code et N° de fiche) ; aucune liaison sans clic | Registre suivant : « Oui, il a un code », saisir le code : candidates |
| 5.6c | [Patiente 1] [Patiente 2] [Aucune, créer] [Je ne sais pas] | Fait | `etat/conversation.jsx` (`chercherPatientes`), `VueDossier.jsx` | Chaque candidate montre son code, son N° de fiche, ses visites et sa dernière visite |
| 5.6d | Identifiants internes aléatoires | Fait | `uuid4()` pour les dossiers, captures et patientes | Aucun identifiant dérivé de données personnelles |
| 5.7a | Sessions multipages : un registre = un dossier | Fait | `records` unique par sage-femme et session | Plusieurs pages, puces « Page 1 · Identification », « Page 2 · Grossesse actuelle » |
| 5.7b | Renumérisation : dossier existant affiché, choix de ce qui est mis à jour | Fait | `renumeriser()`, `components/CarteRenumerisation.jsx` (tableau compact) | Deux pages du même type : « 6 différences sur 8 champs », [Tout garder l'existant] [Tout prendre de la nouvelle photo], choix ligne par ligne. Une page portant un autre N° de fiche est d'abord signalée comme appartenant peut-être à une autre patiente (parcours R3) |
| 5.8 | Image d'origine liée au dossier, à la date de capture, à la sage-femme et au statut de traitement, accès selon le rôle | Fait | `captures` ; `GET /captures/{id}`, `GET /captures/{id}/image` (rôle, journal) ; `VueDossier.jsx` | Vue dossier : « Photo prise le … par sf_… · Lu par l'IA », [Voir la photo d'origine]. Une autre sage-femme reçoit « Photo réservée… » |

## Contraintes (sections 4 et 5)

| Exigence | État | Où | Comment vérifier |
|---|---|---|---|
| Aucun identifiant direct stocké ni affiché | Fait | Prompts (ne jamais lire), clés interdites hors schéma et refusées par `valider.py`, filtre téléphone et CIN du backend, profil sans nom | Aucun nom, CIN, téléphone ni adresse dans le dossier ni dans la copie synchronisée (test `test_cycle_de_vie`) |
| Images d'origine et fichiers de référence jamais modifiés | Fait | Stockage de l'image reçue telle quelle (sha256 conservé) ; `data/` en lecture seule | `GET /captures/{id}` : même sha256 que le fichier envoyé |
| Stockage local chiffré | Fait | `lib/coffre.js` | Voir 5.4a |
| Aucune donnée réelle envoyée à un service tiers | Fait | Seules les pages synthétiques sont lues par l'API Anthropic ; le système central est local et simulé | En production, il faudrait un fournisseur approuvé ou un modèle local (voir les limites du README) |
| Rien hors périmètre (triage, diagnostic, recommandation) | Fait | Statuts neutres sans couleur ; tableau de bord en intervalles descriptifs | Aucun vert, jaune ou rouge ; aucun conseil médical |

## Section 6 : livrables

| Exigence | État | Où |
|---|---|---|
| Code source : extraction, flux conversationnel, file hors ligne, liaison | Fait | `extraction/`, `frontend/`, `backend/` |
| Prototype conversationnel de type WhatsApp | Fait | `frontend/` (application web mobile, conversation) |
| README : installation, choix de conception, cycle de vie, limites, outils et modèles, résultats de l'évaluation | Fait | `README.md`, plus `shared/`, `extraction/`, `backend/`, `frontend/` et `evaluation/README.md` |
| Démonstration : capture hors ligne, retour de la connexion, champ incertain, correspondance | Fait (vidéo à enregistrer) | Parcours jouable de bout en bout ; scénario dans le bilan de l'équipe |

## Section 7 : critères d'évaluation (correspondance)

| Critère | Éléments du projet |
|---|---|
| Qualité de l'extraction (30) | 100 % des valeurs et 98,84 % des champs entièrement exacts sur le dev ; robustesse mesurée sur six dégradations |
| Gestion de l'incertitude (20) | 6 statuts ; confiance finale calibrée (ECE de 11,76 % à 0,76 %) ; seuil de 0,92 ; « l'agent dit quand il doute » |
| Flux de vérification (20) | Questions une à une, quatre réponses égales, bilan de page, saisie manuelle complète, sessions multipages, renumérisation |
| Robustesse hors ligne (15) | Coffre chiffré, journal des photos, reprise automatique, coupure en pleine lecture, échec et reprise de synchronisation |
| Liaison et confidentialité (10) | Code aléatoire ou choisi par la sage-femme, candidates sans création automatique, aucun identifiant direct, image d'origine selon le rôle |
| Code et documentation (5) | README à la racine et par dossier, 29 tests backend et 42 tests d'évaluation, ce tableau |

## Section 8 : bonus (le bac à sable WhatsApp est exclu de la demande)

| Bonus | État | Où | Comment vérifier |
|---|---|---|---|
| Bac à sable WhatsApp réel | Manquant (exclu) | — | — |
| Écriture arabe et pages multilingues | Partiel | Noto Naskh Arabic embarquée (caractères arabes), `dir="auto"` sur toutes les valeurs ; transcription « telle quelle » dans le prompt | Saisir « مستشفى الحسني » dans un champ texte : affiché de droite à gauche (parcours R4). Non fait : aucune mesure de l'extraction sur de l'arabe, absent des pages 1 à 48 de dev |
| Qualité de l'image vérifiée sur l'appareil | Fait | `lib/qualitePhoto.js`, seuils calibrés (48/48 floues et 48/48 sombres détectées, 0/48 originaux) | Photo floue ou sombre : conseil, [Reprendre la photo] ou [Envoyer quand même] |
| Tableau de bord d'agrégats anonymisés | Fait | `GET /tableau-de-bord?source=`, `pages/TableauBord.jsx` | Onglet Tableau de bord : « À quoi sert ce tableau ? », dossiers validés ou données de démonstration (CSV synthétique, bandeau), parts dépistées et positives (VIH, syphilis, hépatite C), tension et température en barres ; moins de 5 dossiers → « — » avec une seule note par indicateur |
| Interface bilingue français / anglais | Fait | `i18n/fr.js`, `i18n/en.js` (mêmes clés, vérifiées) | Réglages, EN : tout le fil est retraduit |

## Section 9 : conseils suivis

| Conseil | Mise en œuvre |
|---|---|
| Partir du schéma, pas de l'OCR | Outil de sortie généré depuis le schéma |
| L'information manquante est un état à part entière | `NON_FOURNI`, `ILLISIBLE`, `NON_APPLICABLE` et `INCONNU`, jamais de « N/A » |
| La confiance par champ décide des questions | Seuil de 0,92 calibré |
| Mode hors ligne en machine à états, testé en coupant en cours de route | États de la file et du dossier ; parcours R1 et R3 |
| Tester tôt sur des photos dégradées | 288 images dégradées évaluées ; contrôle de qualité calibré dessus |

## Corrigé ou ajouté pendant cette vérification

- Cycle de vie : `ENREGISTRE`, `SYNCHRONISE` et `ECHEC_SYNCHRONISATION` n'étaient atteignables par aucun chemin.
  Ajout de l'enregistrement, de la synchronisation idempotente vers le système central simulé (panne simulée,
  reprise automatique) et de 4 tests.
- Saisie manuelle complète : seul le premier champ restait saisissable après un enregistrement.
- Page ajoutée à un dossier déjà validé : erreur 409. Le dossier repasse désormais en révision.
- Doublon suspecté : le dossier existant remplaçait le registre en cours. Désormais, l'application propose de
  l'ouvrir sans les mélanger.
- Code de liaison : la sage-femme peut créer une patiente avec le code qu'elle a déjà écrit sur le registre.
- Image d'origine : date de capture, sage-femme et état de traitement affichés à côté de la photo.
- File « En attente de traitement IA » nommée ainsi à l'écran ; police arabe embarquée.
