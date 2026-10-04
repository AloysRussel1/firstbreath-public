# Conventions communes FirstBreath – à lire par toute l'équipe

Source unique de vérité : `schema_champs.json` (les champs) et `statuts.json` (statuts et états).
Personne ne crée de champ, de statut ou d'état qui n'y est pas. Un changement se discute en équipe, Aloys le fait.

## 1. Noms des champs
- Toujours la clé exacte du schéma : `grossesse.tests.vih`, `pp_precoce.mere.tension`…
- Visites de grossesse : `grossesse.visites[i].champ`, i de 0 à 8 dans cet ordre :
  0 T1_V1, 1 T1_V2, 2 T1_V3, 3 T2_V1, 4 T2_V2, 5 T2_V3, 6 MOIS_7, 7 MOIS_8, 8 MOIS_9.
- Identifiants en majuscules sans accent (A_REVISER, TRAITE_IA) ; libellés avec accents uniquement à l'affichage.

## 2. Format des valeurs
| Type | Format | Exemple |
|---|---|---|
| date | AAAA-MM-JJ | 2026-02-03 (papier : 03/02/2026) |
| decimal | point décimal | 58.8 (papier : 58,8) |
| tension | "SYS/DIA" en mmHg | "110/70" (papier « 11/7 » -> "110/70") |
| booleen | true / false | case cochée, « Oui » -> true |
| choix | valeur exacte de la liste | "NEGATIF" (papier « Neg ») |

## 3. Quel statut choisir ?
| Ce qu'on voit sur le papier | statut | valeur |
|---|---|---|
| Valeur lisible, cohérente | CONNU | la valeur |
| « RAS », « Néant », « Aucun » | CONNU | "RAS" |
| Case vide, tiret « — », ligne vide | NON_FOURNI | null |
| Écrit « inconnu », « ? », « ne sait pas » | INCONNU | null |
| Écriture impossible à lire | ILLISIBLE | null |
| Sans objet (indication de césarienne si voie basse, visite pas encore faite) | NON_APPLICABLE | null |
| Valeur lue mais douteuse ou hors plage plausible | A_REVISER | la meilleure lecture |
Jamais de « N/A » : il faut toujours dire POURQUOI la valeur manque.

Case à cocher unique de type oui/non (ex. grossesse à risque, consanguinité, grossesse désirée) : cochée -> true, non cochée -> false, statut CONNU dans les deux cas. Liste de cases (ex. types de risque) : on liste les cases cochées ; si la question ne s'applique pas, statut NON_APPLICABLE.

## 4. Confiance
- Nombre entre 0 et 1, par champ.
- Si confiance < `seuil_question_suivi` (0.92 dans statuts.json, fixé par la calibration du dev : voir evaluation/README.md ; 0.75 auparavant) -> statut A_REVISER et l'agent pose une question.
- Valeur hors `plage_plausible` du schéma -> A_REVISER, quelle que soit la confiance du modèle.

## 5. Confidentialité (non négociable)
- Jamais stockés : nom, prénom, nom du mari, CIN, téléphone, adresse (voir `champs_interdits`).
- Pour le personnel (« Examen fait par Dr X ») : on garde seulement la fonction (MEDECIN, SAGE_FEMME, INFIRMIER).
- Identifiants internes : uuid aléatoires uniquement.
- Images d'origine et fichiers de `data/` : jamais modifiés.

## 6. Vérifier avant de livrer
    python shared/valider.py mon_fichier.json
- Extraction : chaque sortie de extract_page() doit passer.
- Évaluation : la vérité terrain doit passer.
- Backend : rejeter toute donnée qui ne passe pas.

## 7. Cas particuliers
- Liste de cases sans aucune case cochée alors que la question s'applique (ex. signes de danger, vaccins du jour) :
  si la consultation a eu lieu (date de consultation remplie) -> CONNU avec une liste vide `[]` ;
  si la section entière est vide -> NON_FOURNI.
- Antécédents familiaux (deux colonnes « Famille de la femme » et « Mari/famille ») : un seul champ texte,
  "RAS" si les deux colonnes disent RAS, sinon "femme : <colonne 1> ; mari : <colonne 2>" (ex. "femme : Père ; mari : RAS").
- `obstetrique.accouchements_anterieurs` : liste d'objets, un par accouchement antérieur rempli, avec les clés
  `date`, `modalite`, `indication_cesarienne`, `complication`, `poids_g`, `complication_nouveau_ne`
  (valeurs normalisées : date AAAA-MM-JJ, poids_g entier, « RAS » pour rien à signaler ; absence = null).
  Ex. `{"date": "2022-11-12", "modalite": "Voie basse", "indication_cesarienne": null, "complication": "RAS", "poids_g": 3626, "complication_nouveau_ne": "RAS"}`.
- Tableau des anomalies des grossesses antérieures : case « Nombre » vide -> NON_FOURNI.
- Niveau d'instruction : "Aucun" est une valeur (pas de scolarisation), pas RAS.
