# Tâche 1 – Appli de chat (Aloys) · dossier frontend/ · branche front
Points visés : vérification 20, hors ligne 15 (partie client), liaison 10 (écran de choix).

## Mission
Tout ce que la sage-femme voit et touche, plus le stockage chiffré sur le téléphone.
Ensuite : intégration finale des briques et vidéo de démo.

## Stack et prérequis
- React 19 + Vite (déjà installés dans frontend/).
- dexie pour IndexedDB. Installation : `npm install dexie` (dans frontend/).
- Web Crypto natif du navigateur pour le chiffrement (AES-GCM), aucune bibliothèque de chiffrement.
- `crypto.randomUUID()` pour tous les identifiants.
- CSS simple, sans framework.
- URL de l'API lue dans `import.meta.env.VITE_API_URL` ; tous les appels serveur dans `src/api.js`.
  Vite ne lit que les .env de frontend/ : pour utiliser le .env racine, mettre `envDir: '..'` dans vite.config.js.
- Bonus optionnel : vite-plugin-pwa (installation hors ligne de l'appli).

## Étapes
1. Chat type WhatsApp : fil de messages, envoi de photo, session multipage (plusieurs pages = un seul dossier).
2. Affichage du dossier (simulé avec shared/exemple_dossier.json), regroupé par section,
   libellés de shared/schema_champs.json, couleur selon le statut et la confiance.
3. Vérification : Confirmer / Corriger / Reprendre la photo ; questions de suivi pour les champs
   A_REVISER, ILLISIBLE ou sous le seuil de confiance ; saisie manuelle complète si l'IA est indisponible.
4. Hors ligne : bouton « Simuler hors ligne », IndexedDB chiffré (Web Crypto AES-GCM), file d'attente,
   état visible de chaque enregistrement (statuts.json).
5. Correspondance patiente : [Patiente 1] [Patiente 2] [Aucune, créer] [Je ne sais pas].
6. Branchement sur l'API réelle (Tâche 4) via src/api.js, puis vidéo de démo.

## Terminé quand
La démo montre les 4 moments exigés : capture hors ligne, retour du réseau et synchronisation,
révision d'un champ incertain, décision de correspondance.

## Prompt Claude Code
```
Je travaille dans frontend/ (branche front). Lis CLAUDE.md, GUIDE_EQUIPE.md, frontend/TACHE.md et tout le dossier shared/. Vérifie avec python shared/valider.py shared/exemple_dossier.json, résume ma tâche en 10 lignes, puis attends mon accord. Ensuite réalise les étapes de frontend/TACHE.md une par une : après chaque étape, arrête-toi, explique comment tester avec npm run dev et propose un message de commit. Tous les appels serveur dans un seul fichier src/api.js, simulés pour l'instant. Ne modifie que frontend/. Je suis sous Windows avec PowerShell.
```
