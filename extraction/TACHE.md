# Tâche 2 – Lecteur IA · dossier extraction/ · branche extraction
Points visés : extraction 30, et une grande partie de l'incertitude 20. C'est la brique la plus importante.

## Mission
Transformer une photo de page en objet structuré conforme à shared/ :
`extract_page(image_path) -> {"type_page": ..., "champs": [...]}` (signature fixée dans shared/CONTRAT.md).

## Stack et prérequis
- Modèle de vision Claude via le SDK Python `anthropic`.
  Modèle par défaut : `claude-sonnet-5` ; `claude-opus-5-5` pour les pages difficiles ou les relectures.
- Sortie JSON structurée via tool use (un outil dont le schéma reprend les clés de shared/schema_champs.json).
- `python-dotenv` pour charger ANTHROPIC_API_KEY depuis le .env racine.
- `Pillow` pour redimensionner et redresser les images avant l'envoi.
- `hashlib` pour dédupliquer les images identiques.
- Installation : `pip install -r extraction/requirements.txt` (venv activé, depuis la racine).
- Seules des données synthétiques (celles du ZIP DayOne) sont envoyées à l'API, conformément aux consignes.
- Le modèle utilisé doit être cité dans le README.

## Étapes
1. Choisir un modèle de vision (à citer dans le README), clé d'API dans .env, premier appel sur une image de data/.
2. Détecter le type de page parmi les 8 types de shared/statuts.json.
3. Un prompt par type de page, qui demande EXACTEMENT les clés de shared/schema_champs.json, en JSON.
   Ordre : IDENTIFICATION (le N° de fiche est essentiel), puis GROSSESSE_ACTUELLE
   (signes vitaux, VIH, syphilis, hépatites), puis ANTECEDENTS, puis les autres.
4. Normaliser les valeurs (dates AAAA-MM-JJ, tension "110/70", « Neg » -> NEGATIF…)
   et attribuer les statuts selon shared/CONVENTIONS.md.
5. Filtre de confidentialité : aucune clé ni valeur interdite ne sort (nom, nom du mari, CIN, téléphone, adresse).
6. Chaque sortie doit passer shared/valider.py.
   LIVRER UNE PREMIÈRE VERSION VERS H4 et prévenir les Tâches 3 et 4.
7. Améliorer les prompts selon les erreurs remontées par la Tâche 3.

## Conseils
- Beaucoup de PNG sont des doublons identiques : dédupliquer par hash.
- Tester tôt sur les vraies photos dégradées data/Paper Registry/1-*.jpg.
- Demander au modèle de signaler son doute plutôt que de deviner.

## Terminé quand
extract_page() fonctionne sur les 8 types de page, toutes les sorties sont valides, le score est mesuré par la Tâche 3.

## Prompt Claude Code
```
Je travaille dans extraction/ (branche extraction). Lis CLAUDE.md, GUIDE_EQUIPE.md, extraction/TACHE.md et tout le dossier shared/. Résume ma tâche en 10 lignes, puis attends mon accord. Ensuite réalise les étapes de extraction/TACHE.md une par une, en t'arrêtant après chacune pour que je teste sur des images de data/. extract_page() doit garder exactement la signature de shared/CONTRAT.md et chaque sortie doit passer shared/valider.py. Clé d'API dans .env. Ne modifie que extraction/. Je suis sous Windows avec PowerShell.
```
