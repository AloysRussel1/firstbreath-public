# FirstBreath — scénario de la vidéo de démonstration (environ 3 minutes)

La vidéo montre les quatre moments demandés par les consignes :

1. une capture hors ligne ;
2. le retour de la connexion et la synchronisation ;
3. la révision d'un champ incertain : page 9, le « 4 » du N° de fiche lu « A » ;
4. une décision de correspondance.

Elle montre aussi le tableau de bord et l'interface bilingue.

Le registre principal est celui d'une même patiente, la patiente 2 du spécimen :

| Page | Fichier | Type | Questions |
|---|---|---|---|
| 9 | `dossiers_specimen_10_patientes-09.png` | Identification | 1 : le N° de fiche lu « 2026-A16-002 » au lieu de « 2026-416-002 » |
| 13 | `dossiers_specimen_10_patientes-13.png` | Post-partum précoce, mère | 1 |
| 14 | `dossiers_specimen_10_patientes-14__1NRsJ9Ddo8.png` | Post-partum précoce, nouveau-né | 0 |

La page 1 (`dossiers_specimen_10_patientes-01.png`, patiente 1) sert à la décision de correspondance.

## Préparation avant de filmer

1. **Serveur.** Arrêter tout ancien serveur sur le port 8000, puis démarrer avec une base vide :
   ```powershell
   $env:EXTRACTION_FOURNISSEUR = "anthropic"          # lectures déjà en cache : aucun coût
   $env:FIRSTBREATH_DATA_DIR = "$env:TEMP\firstbreath_demo"
   .venv\Scripts\uvicorn.exe backend.main:app --port 8000
   ```
   Sans clé d'API, `EXTRACTION_FOURNISSEUR=simule` montre le parcours, mais sans les vraies lectures.
2. **Interface.** `cd frontend`, puis `npm run dev`, puis ouvrir `http://localhost:5173`. Pour filmer un téléphone,
   utiliser les outils de développement du navigateur en largeur 390 px.
3. **Appareil.** Réglages → « Effacer les données de l'appareil ». Vérifier que la langue est en français et que
   la panne simulée et « Simuler hors ligne » sont désactivées.
4. **Fichiers.** Garder les quatre fichiers ci-dessus à portée dans l'explorateur. Le bouton appareil photo
   ouvre le sélecteur de fichiers sur ordinateur.

## Déroulé

| Temps | Moment | À l'écran | À dire |
|---|---|---|---|
| 0:00–0:15 | Accueil | Page d'accueil, puis profil `sf_demo`, Sage-femme | « Le registre papier reste la référence ; FirstBreath s'y greffe. » |
| 0:15–0:40 | **1. Capture hors ligne** | « Simuler hors ligne » ; photographier la page 9 puis la page 14. La ligne de résumé affiche « 2 pages · 2 en cours » ; la légende « ? » explique l'icône hors ligne. Recharger la page : les photos sont toujours là. | « Sans réseau, la photo est chiffrée sur le téléphone et mise en file. Rien n'est perdu, même en rechargeant. » |
| 0:40–1:00 | **2. Retour de la connexion** | « Rétablir la connexion » : l'envoi et la lecture se font seuls (« Je lis la photo 1… »). La page 14 n'a aucun doute ; l'identification en a 1. | « Au retour du réseau, tout repart automatiquement. L'agent ne pose une question que lorsqu'il doute. » |
| 1:00–1:35 | **3. Champ incertain** | « Question 1 sur 1 » : N° de la fiche, « J'ai lu 2026-A16-002 », confiance 60 %. Toucher la vignette pour agrandir la photo et montrer le « 4 ». [Corriger] ouvre la zone de saisie en bas ; taper `2026-416-002`, [Envoyer]. Le bilan affiche « Corrigé (1) ». | « Les quatre réponses ont le même poids : confirmer n'est pas plus facile que corriger. » |
| 1:35–1:55 | Validation qui s'explique | [Photographier la page suivante] : page 13, 1 question. Avant d'y répondre, toucher « Valider le dossier » : le message dit « Il reste 1 question », nomme le champ, avec [Vérifier]. Répondre ; le message devient « Tout est vérifié » ; [Valider le dossier]. | « La validation dit précisément ce qui manque. » |
| 1:55–2:30 | **4. Décision de correspondance** | « Non, pas de code » → « Créer une patiente » : le code (par exemple `XK7-3PA`) est à recopier sur le registre ; [J'ai recopié le code] ; « enregistré » puis « synchronisé ». Ensuite, dans la ligne des pages, « + Nouveau registre » ; photographier la page 1 ; Valider ; « Oui, il a un code » ; taper le code. Les choix s'affichent : [Patiente 1 · code … · N° de fiche 2026-416-002 · 1 visite] [Aucune, créer] [Je ne sais pas]. Le N° de fiche diffère : [Je ne sais pas]. | « L'application propose, la sage-femme tranche ; rien n'est jamais lié ni créé automatiquement. » |
| 2:30–2:45 | Dossiers | Onglet Dossiers → la carte de la patiente → la vue du dossier → « Voir la photo d'origine » (date, sage-femme, état de traitement). | « L'image d'origine reste liée au dossier, avec un accès selon le rôle. » |
| 2:45–3:00 | Tableau de bord | « À quoi sert ce tableau ? » ; moins de 5 dossiers validés → [Voir les données de démonstration] ; le bandeau « Données synthétiques » ; les tuiles (95 % dépistées pour le VIH, positifs « — ») ; les barres de tension. | « Des tendances anonymes ; toute case de moins de 5 dossiers est masquée ; aucun avis médical. » |
| 3:00–3:10 | Bilingue | Réglages → EN : la conversation et le tableau de bord sont retraduits. | « Interface entièrement bilingue. » |

## Si quelque chose ne se passe pas comme prévu

- **« Doublon suspecté »** : la photo a déjà été envoyée sur ce serveur. Repartir d'un `FIRSTBREATH_DATA_DIR` vide
  et effacer les données de l'appareil.
- **Champs vides et « 0 lus avec certitude »** : le serveur tourne en mode simulé (avis « Mode sans lecture »
  dans le fil). Relancer avec `EXTRACTION_FOURNISSEUR=anthropic`.
- **Plus grand écran** : au-delà de 1100 px, le dossier en cours s'affiche à côté du fil, ce qui permet de
  montrer la vérification sans changer d'écran.
