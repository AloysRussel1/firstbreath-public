# FirstBreath — pitch de 3 minutes

## Plan

| Temps | Partie | Contenu | À montrer |
|---|---|---|---|
| 0:00–0:25 | Le problème | Le registre papier ne suit pas la femme d'une visite à l'autre et ne remonte pas au système de santé. La contrainte : zéro changement pour la sage-femme. | Photo d'une page du registre (spécimen) |
| 0:25–0:50 | La solution | Un agent de type WhatsApp : photo, lecture selon 245 champs, une question seulement en cas de doute, liaison des visites par un code recopié sur le papier. | Écran de conversation avec une question |
| 0:50–1:40 | Démo éclair | Capture hors ligne, retour du réseau, le « 4 » lu « A » sur la page 9 corrigé en un geste, décision de correspondance. | Extraits de la vidéo (`docs/DEMO.md`) |
| 1:40–2:20 | Les chiffres | Score officiel sur le jeu de test, calibration, seuil de 0,92. | `evaluation/figures/calibration_dev.png`, `evaluation/figures/compromis_seuil_dev.png` |
| 2:20–2:45 | Confiance et confidentialité | Statuts explicites, aucun identifiant direct, image d'origine selon le rôle, stockage chiffré, tableau de bord anonymisé (cases de moins de 5 masquées). | Tableau de bord avec données de démonstration |
| 2:45–3:00 | La suite | Modèle open source hébergé par le système de santé, vérification par section, WhatsApp Business. | — |

## Chiffres clés

**Jeu de test** : patientes 7 à 10, 32 pages, jamais vues pendant le développement ; évaluation lancée une seule
fois, modèle gelé.

| Indicateur | Valeur |
|---|---|
| Valeurs exactes | **98,92 %** (547/553) |
| Statuts exacts | 54,28 % (336/619) |
| Champs entièrement exacts (valeur et statut) | 53,63 % (332/619) |
| Valeurs fausses sans alerte (seuil 0,92) | **0,65 %** (4/619) |
| Questions par page, en moyenne | 11,4 (médiane 3,5) |

Lecture : les valeurs lues sont presque toujours justes ; l'écart sur les statuts vient du seuil prudent de 0,92,
qui envoie en question 224 champs pourtant bien lus. Ce sont des questions de plus, pas des erreurs silencieuses.

**Développement** (patientes 1 à 6) :
- 100 % de valeurs exactes (1 028/1 028) et 98,84 % de champs entièrement exacts ;
- robustes à l'ombre, à la sous-exposition et au JPEG ;
- le flou et la rotation font nettement baisser la qualité, d'où le contrôle de qualité sur l'appareil.

**Calibration** : l'erreur de calibration (ECE) passe de 11,76 % à 0,76 %. Le seuil de 0,92 ne laisse passer
aucune erreur sur 1 280 champs non révisés, en vérification sur les patientes 5 et 6.

**Hors ligne** : les 12 états du cycle de vie sont atteints dans l'application. Aucune photo n'est perdue, même
après un rechargement immédiat ou une coupure en pleine lecture.

## Graphiques

1. `evaluation/figures/calibration_dev.png` : la confiance annoncée contre l'exactitude réelle, avant et après
   calibration. Message : quand l'agent dit « 95 % », il a raison 95 fois sur 100.
2. `evaluation/figures/compromis_seuil_dev.png` : la charge de révision contre l'erreur résiduelle selon le
   seuil. Message : nous avons choisi la sécurité (0 erreur résiduelle observée), au prix de plus de questions.

## Questions probables du jury

**Confidentialité : où vont les données ?**
- Les noms, CIN, téléphones et adresses ne sont jamais lus ni stockés. Le prompt l'interdit, le schéma ne
  contient pas ces champs, et le serveur filtre les valeurs suspectes.
- Sur le téléphone, tout est chiffré (AES-GCM). La photo d'origine n'est visible que par la sage-femme qui l'a
  prise et par un superviseur, et chaque accès est journalisé.
- Le système de santé ne reçoit qu'une copie anonymisée, sans image.
- Pour ce défi, seules des pages synthétiques ont été envoyées à l'API. Les photos `1-*.jpg`, qui semblent
  réelles, n'ont jamais été envoyées.

**Combien de questions la sage-femme doit-elle répondre ?**
- En moyenne 11,4 (médiane 3,5) par page sur le jeu de test. Les pages simples n'en posent presque aucune, mais une page de
  grossesse difficile peut en poser beaucoup (65 en moyenne, jusqu'à 156).
- C'est un choix assumé : aucune erreur silencieuse.
- Les pistes : vérification par section, seuil par type de champ, et « Tout confirmer » pour les champs sûrs
  (jamais pour les doutes).

**Comment passer en production ?**
- Remplacer l'API par un modèle de vision open source hébergé par le système de santé ou le ministère : le
  pipeline est isolé derrière `extract_page()`, et le contrat de sortie ne change pas.
- Recalibrer le seuil sur de vraies photos, annotées par des sages-femmes.
- Brancher l'agent sur WhatsApp Business.
- Ajouter une vraie authentification des rôles et un serveur central réel à la place du système simulé.

**Et si l'agent se trompe sans le dire ?**
- C'est ce que mesure « valeurs fausses sans alerte » : **0,65 %** (4/619) sur le test.
- Le registre papier reste la référence, et la photo d'origine est toujours consultable.

**Et sans connexion pendant des jours ?**
- La capture et la file fonctionnent sans réseau, et les photos restent chiffrées sur le téléphone.
- La lecture, la liaison et la synchronisation reprennent seules au retour du réseau.
