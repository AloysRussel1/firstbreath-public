# Contrat commun – ne change qu'avec l'accord de toute l'équipe

## Interface du pipeline (Tâche 2 -> utilisé par Tâches 3 et 4)
    from extraction.pipeline import extract_page
    extract_page(image_path: str) -> dict   # {"type_page": ..., "champs": [ ... ]}
Chaque champ : {champ, valeur, statut, confiance (0-1), page_source}.
Aucun champ de shared/statuts.json["champs_interdits"] ne doit jamais sortir.

## Routes API (Tâche 4 -> utilisées par Tâche 1)
    POST  /captures                 image + session_id + page_no + sage_femme_id -> dossier, etat CAPTURE
    POST  /captures/{id}/traiter    lance l'extraction -> TRAITE_IA ou A_REVISER
    GET   /dossiers/{id}            dossier complet
    PATCH /dossiers/{id}/champs     confirmer / corriger un champ
    GET   /patientes/correspondances?numero_fiche=...   -> liste de candidates
    POST  /dossiers/{id}/lier       {"patiente_id": "..."} | {"choix": "nouvelle"} | {"choix": "inconnu"}
    POST  /sync                     lot d'enregistrements en file d'attente
    GET   /sante                    pour tester la connexion

## Règles
- Identifiants internes aléatoires (uuid), jamais dérivés d'informations personnelles.
- Images d'origine et fichiers de référence jamais modifiés.
