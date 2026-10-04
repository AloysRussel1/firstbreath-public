# FirstBreath — interface (frontend)

Application web mobile pour les sages-femmes. Elles photographient les pages du registre papier de maternité, puis
vérifient dans une conversation les seules informations dont la lecture est douteuse. L'application fonctionne
hors ligne et relie les visites d'une même patiente grâce à un code court recopié sur le registre.

React 19 + Vite. Aucune ressource n'est chargée depuis Internet : polices embarquées, icônes SVG en ligne.

## Lancer

```bash
# 1. Backend (depuis la racine du dépôt, venv activé)
uvicorn backend.main:app --port 8000

# 2. Interface
cd frontend
npm install
npm run dev        # http://localhost:5173
npm run build      # production dans dist/ ; npm run preview pour la servir
npm run lint
```

Le serveur est lu dans `VITE_API_BASE_URL` (par défaut `http://127.0.0.1:8000`). Le backend autorise les
origines `FIRSTBREATH_CORS_ORIGINS` (par défaut `localhost:5173` et `127.0.0.1:5173`).
Sans clé d'API, `EXTRACTION_FOURNISSEUR=simule` donne une confiance de 0 à chaque champ : chacun devient une question.

## Écrans et parcours

| Route | Écran |
|---|---|
| `#/accueil` | Vitrine : promesse, trois étapes 01/02/03, illustration du registre |
| `#/profil` | Identifiant professionnel (jamais le nom) et rôle : sage-femme ou superviseur |
| `#/a-propos` | Principes : registre papier de référence, statuts neutres, anonymat |
| `#/app/conversation` | Vérification : photo → lecture → questions → validation → liaison |
| `#/app/dossiers[/<id>]` | Patientes par code, dossiers non reliés, vue détaillée d'un dossier |
| `#/app/tableau` | Tableau de bord anonymisé : explication, source « Dossiers validés » ou « Données de démonstration » (CSV synthétique, bandeau), indicateurs clés, tension et température en barres |
| `#/app/reglages` | Langue, profil, connexion simulée, file d'attente, synchronisation (et panne simulée), contrôle de qualité, effacement |

**Parcours principal (conversation)**
1. La sage-femme photographie une page. Un contrôle sur l'appareil vérifie la netteté et la luminosité. Si la photo
   est floue ou sombre, l'application donne un conseil de prise de vue : [Reprendre la photo] ou [Envoyer quand même].
2. Hors ligne, la photo est chiffrée et mise en file « En attente de traitement IA ». Au retour du réseau, elle part
   toute seule ; une coupure pendant la lecture ne perd rien.
3. L'agent annonce la lecture (« je lis la page »), puis résume : « 160 informations lues, 1 à vérifier ».
4. Chaque doute devient une question, une seule à la fois (« Question 2 sur 5 ») : vignette de la page
   (agrandissable), valeur lue, raison du doute en une phrase, puis quatre réponses de même taille :
   **Confirmer · Corriger · Vide sur le papier · Reprendre la photo**.
5. Fin de page : bilan (confirmé, corrigé, laissé vide) puis action suivante : [Photographier la page suivante],
   [Valider le dossier] ou [Voir le détail]. [Tout confirmer] ne confirme que les champs lus avec certitude.
   Si la lecture échoue : [Relancer la lecture], [Reprendre la photo] ou [Saisir à la main], pour une saisie
   complète de la page.
6. Liaison : « Le registre porte-t-il déjà un code ? » La sage-femme saisit le code ou cherche par N° de fiche.
   L'application propose alors [Patiente 1] [Patiente 2] … [Aucune, créer] [Je ne sais pas], avec le code, le
   N° de fiche, le nombre de visites et la date de la dernière visite de chaque patiente.
   Pour une nouvelle patiente, l'application génère un code (`XXX-XXX`, sans 0/O ni 1/I) à recopier en haut de la
   page d'identification. Si le registre porte déjà un code écrit par la sage-femme et que personne ne l'a,
   elle peut créer la patiente avec ce code.
   Ensuite, le dossier est enregistré, puis synchronisé avec le système de santé (copie anonymisée). En cas de
   panne, il passe en « Échec de synchronisation » et repart au retour de la connexion. Le registre se termine
   par [Ouvrir le dossier] ou [Nouveau registre].
7. Page d'une autre patiente (N° de fiche différent) : « Cette page semble appartenir à une autre patiente » avec
   [L'ajouter quand même] [Commencer un nouveau registre] [Annuler].
   Renumérisation : si une page du même type est photographiée de nouveau, un tableau compact montre seulement les
   champs différents (« 6 différences sur 8 champs »), avec [Tout garder l'existant] [Tout prendre de la nouvelle
   photo] et un choix ligne par ligne. Le dossier existant est gardé par défaut ; la sage-femme choisit ce qu'elle remplace. Une photo
   identique déjà envoyée est un doublon suspecté : l'application propose d'ouvrir le dossier existant.

**Dossiers** : patientes groupées par code, avec l'historique de leurs visites. La vue d'un dossier présente
ses sections, des cartes de visites (seules les visites faites sont dépliées), les statuts neutres, la photo
d'origine (date de capture, sage-femme, état de traitement) et l'historique des états. Depuis cette vue, on peut
relier plus tard un dossier validé, l'enregistrer ou relancer sa synchronisation.

**Mise en page** : sur téléphone, le fil occupe toute la largeur (marges de 12 à 16 px). Sur tablette et
ordinateur, il se centre jusqu'à 900 px. Au-delà de 1100 px, le dossier en cours s'affiche dans un panneau à côté
du fil. Les données sont en lignes compactes « libellé : valeur » avec l'icône de statut, sur deux colonnes quand
la section est assez large. Les sections se replient et leur en-tête indique le nombre de champs et de points à
vérifier. Les visites s'affichent en vrai tableau sur grand écran, en cartes sinon. Le fil défile seul vers le
dernier message, sauf pendant une relecture : « Nouveaux messages ↓ » s'affiche alors.

## Choix de conception

- **Conversation plutôt que formulaire.** Une page compte jusqu'à 160 champs. La sage-femme ne voit que ce qui
  demande son œil, une question à la fois, dans un fil qu'elle connaît (type WhatsApp). Le détail complet reste à un
  geste (« Voir le détail »).
- **Statuts neutres.** Aucun vert, jaune ou rouge : la forme (icône pleine, pointillée, barrée) et le libellé
  distinguent les statuts. Le bleu-vert de la marque est réservé à l'en-tête, au logo, au bouton photo et à la
  navigation, jamais à un statut ; le gris secondaire n'est jamais utilisé pour une valeur lue ni pour une question.
  Contraste AA au minimum, 7:1 pour le texte courant.
- **Contre le biais d'automatisation.** Les quatre réponses ont la même taille et le même poids : confirmer n'est
  pas plus facile que corriger. « Confirmer » est désactivé quand rien n'a été lu. Un doute ne se confirme jamais en
  masse. Dans la renumérisation, rien n'est présélectionné en faveur de la nouvelle lecture. La liaison n'est jamais
  automatique : « Je ne sais pas » est toujours proposé.
- **Anonymat du tableau de bord.** Le calcul est fait par le serveur (`GET /tableau-de-bord`), sur les dossiers validés
  seulement. Chaque case compte des dossiers distincts. Toute case de moins de 5 dossiers, total compris, est
  remplacée par « Effectif insuffisant pour préserver l'anonymat » : aucun chiffre n'est publié sous ce seuil.
  Les intervalles sont descriptifs, sans aucun avis médical.
- **Stockage hors ligne chiffré.** `lib/coffre.js` (Dexie / IndexedDB) chiffre photos, conversation et listes en
  AES-GCM-256. La clé est non extractible et reste dans le navigateur, avec un IV aléatoire à chaque écriture. Un journal
  des photos en file est écrit avant l'entrée en file. Au rechargement, il est réconcilié avec la conversation
  sauvegardée : aucune photo n'est perdue. Le serveur reconnaît un renvoi identique (même session, page et image) et
  ne crée pas de doublon.
- **Données personnelles.** Aucun nom, CIN, téléphone ni adresse n'est affiché ou stocké. Le profil est un
  identifiant professionnel. Le serveur filtre les valeurs qui ressemblent à un téléphone ou à une CIN.
- **Accès à la photo d'origine selon le rôle** : une sage-femme voit ses propres photos, un superviseur les voit toutes.
  Chaque accès est journalisé côté serveur.
- **Bilingue FR / EN**, bascule instantanée. Les textes de l'agent sont stockés en clés de traduction : changer de
  langue retraduit tout le fil. `dir="auto"` est posé sur les valeurs, et Noto Naskh Arabic est embarquée
  (caractères arabes seulement) : une valeur arabe s'affiche correctement, de droite à gauche, même hors ligne.
- **Lisibilité et accessibilité** : bulles en 16 px, informations secondaires en 14 px, valeurs en semi-gras,
  interligne 1,45, cibles d'au moins 44 px. Le focus est visible et Échap ferme les fenêtres. Les animations de
  150 à 250 ms sont désactivées par `prefers-reduced-motion`. Le zoom à 200 % fonctionne : en faible hauteur,
  l'en-tête et les onglets se compactent.

## Contrôle de qualité des photos

`lib/qualitePhoto.js` réduit l'image à 480 px en niveaux de gris et calcule deux mesures :
- netteté = 1000 × variance du laplacien / luminosité² ;
- luminosité = moyenne des gris.

Les seuils ont été calibrés sur les 48 pages de dev et leurs versions dégradées (`extraction/degrader.py`) :

| Critère | Pages signalées | Originaux signalés |
|---|---|---|
| Netteté < 9 | 48/48 pages floues | 0/48 |
| Luminosité < 110 | 48/48 pages sombres | 0/48 |

Les versions JPEG compressées, tournées et ombrées ne déclenchent aucune alerte. Le contrôle se désactive dans
Réglages.

## Organisation du code

```
src/
  api.js                 seul fichier qui parle au serveur (en-têtes X-Sage-Femme-Id, X-Role ; mode hors ligne simulé)
  App.jsx                routage par « # » et fournisseurs (langue > profil > connexion > conversation)
  etat/                  conversation.jsx (moteur du fil, file, questions, liaison, renumérisation),
                         connexion.jsx, profil.jsx, route.js, donnees.js (lecture serveur + copie chiffrée)
  lib/                   coffre.js, qualitePhoto.js, format.js, textes.js, statuts.js, code.js, preferences.js
  components/            CarteQuestion, CarteRenumerisation, SaisieCode, SectionsDossier, EditeurValeur…
  pages/                 Accueil, Profil, APropos, Application, Conversation, Dossiers, VueDossier, TableauBord, Reglages
  i18n/                  fr.js, en.js
  styles/                theme.css (jetons), base, vitrine, application, conversation, dossiers
```

## Limites connues

- La liaison, le tableau de bord, la photo d'origine et la renumérisation demandent une connexion. Hors ligne, les
  listes et dossiers déjà consultés s'affichent depuis la copie chiffrée.
- La clé de chiffrement vit dans le navigateur : elle protège contre la lecture directe du disque, pas contre une
  personne qui utilise la session ouverte. Il n'y a pas d'authentification réelle : le rôle est déclaré dans le
  profil et envoyé en en-tête.
- Une même image envoyée deux fois est signalée comme doublon suspecté. Avec les photos fixes du jeu de données,
  une vraie visite suivante (même page d'identification rephotographiée) ne peut donc pas être rejouée. La
  renumérisation a été jouée avec deux pages d'identification différentes dans un même registre.
- Le système de santé central est simulé par le serveur.
- Le seuil de surexposition (luminosité > 235) n'a pas pu être calibré : aucune version dégradée ne correspond.
- Les détails techniques des erreurs du serveur ne sont plus affichés : l'agent donne un message simple, en français ou en anglais.
- Le tableau de bord n'affiche pas de médiane : une statistique exacte sur un petit effectif pourrait identifier
  une patiente.
