# Robustesse de l'extraction sur images dégradées

Généré par `extraction/rapport_robustesse.py` en lisant uniquement le cache (aucun appel API).
Modèle : `claude-sonnet-5` ; nouvel essai à effort medium puis low si la sortie est tronquée.

Images : dégradation `combinaison` sur les 48 pages de dev (patientes 1 à 6), 5 autres dégradations sur les patientes 1 et 2 (16 pages chacune) : 128 images. Reproductibles avec `extraction/degrader.py` (pillow==12.3.0).

Référence : extraction de la page propre d'origine (98,9 % de valeurs exactes sur le dev d'après `evaluation/`) ; les champs déjà A_REVISER sur la page propre sont exclus.

Les images dégradées sont classées **avec la confiance finale** (`extraction/confiance.py` : cohérence entre champs et signal de réflexion) ; la section « Effet de la confiance finale » compare avec le classement sans cette couche.

## Vue d'ensemble

| Dégradation | Pages | Valides | Échecs | Accord | Doute justifié | Fausse alerte | **Valeur fausse sans alerte** | Statut changé sans alerte | Coût $ | Temps s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| flou | 16 | 16 | 0 | 61.1% | 14.9% | 22.9% | **0.6%** | 0.4% | 1.12 | 593 |
| rotation | 16 | 16 | 0 | 33.9% | 65.4% | 0.4% | **0.0%** | 0.2% | 1.89 | 1190 |
| ombre | 16 | 16 | 0 | 99.8% | 0.0% | 0.0% | **0.2%** | 0.0% | 0.85 | 328 |
| sombre | 16 | 16 | 0 | 99.6% | 0.0% | 0.2% | **0.2%** | 0.0% | 0.86 | 325 |
| jpeg | 16 | 16 | 0 | 90.8% | 0.2% | 8.4% | **0.6%** | 0.0% | 0.98 | 429 |
| combinaison | 48 | 48 | 0 | 46.7% | 21.6% | 29.7% | **0.2%** | 1.8% | 4.12 | 2399 |
| **total** | 128 | 128 | 0 | 65.7% | 18.2% | 15.1% | 0.3% | 0.7% | 9.83 | 5263 |

Champs comparés : 3907. Coût et temps incluent les essais tronqués (3 essais tronqués ; effort de la lecture retenue : {'défaut': 125, 'medium': 3}).

Statuts des champs par dégradation :

- flou : {'A_REVISER': 186, 'CONNU': 179, 'NON_APPLICABLE': 88, 'NON_FOURNI': 37}
- rotation : {'A_REVISER': 323, 'CONNU': 150, 'NON_APPLICABLE': 8, 'NON_FOURNI': 9}
- ombre : {'A_REVISER': 1, 'CONNU': 354, 'NON_APPLICABLE': 88, 'NON_FOURNI': 47}
- sombre : {'A_REVISER': 1, 'CONNU': 354, 'NON_APPLICABLE': 88, 'NON_FOURNI': 47}
- jpeg : {'A_REVISER': 43, 'CONNU': 312, 'NON_APPLICABLE': 88, 'NON_FOURNI': 47}
- combinaison : {'A_REVISER': 756, 'CONNU': 375, 'NON_APPLICABLE': 278, 'NON_FOURNI': 61}

## Doutes justifiés contre fausses alertes

Sur 1300 champs mis en A_REVISER par les dégradations : 710 doutes justifiés (54.6%) et 590 fausses alertes (45.4%, valeur correcte mais doute exprimé).

Une fausse alerte coûte une question de plus à la sage-femme ; un doute justifié évite une erreur.

## Effet de la confiance finale

| Catégorie | Sans confiance finale | Avec confiance finale |
|---|---:|---:|
| accord | 2824 | 2567 |
| doute justifié | 692 | 710 |
| fausse alerte | 333 | 590 |
| valeur fausse sans alerte | 29 | 11 |
| statut changé sans alerte | 29 | 29 |

- **Valeurs fausses sans alerte attrapées : 18 sur 29** (passées en A_REVISER par la cohérence ou le signal de réflexion).
- **Fausses alertes en plus : 257** (champs identiques à la page propre, désormais A_REVISER).
- Pages propres : aucune nouvelle alerte (les règles de cohérence ne se déclenchent sur aucune des 48 pages propres, et leur ratio de réflexion reste sous le seuil).
- Origine des fausses alertes en plus : {'cohérence': 5, 'réflexion': 252}.

## Valeurs fausses sans alerte (avant confiance finale), par champ

29 champs CONNU avec une valeur différente de la page propre, sans A_REVISER avant la confiance finale (+ 29 changements de statut sans A_REVISER). ✓ = attrapée par la confiance finale.

| Champ | Nombre | Attrapées | Exemples (dégradation, page : propre -> dégradée, confiance, attrapée) |
|---|---:|---:|---|
| `grossesse.visites[*].date_rdv` | 4 | 4 | combinaison p.27 : "2026-04-25" -> "2026-04-23" (0.85, ✓) ; combinaison p.43 : "2026-02-25" -> "2026-02-23" (0.75, ✓) ; combinaison p.43 : "2026-03-20" -> "2026-03-10" (0.75, ✓) |
| `grossesse.visites[*].bcf` | 4 | 4 | combinaison p.43 : 149 -> 139 (0.75, ✓) ; combinaison p.43 : 144 -> 148 (0.75, ✓) ; combinaison p.43 : 139 -> 151 (0.75, ✓) |
| `profil.niveau_instruction` | 3 | 2 | flou p.2 : "Lycée" -> "Cycle" (0.80) ; combinaison p.18 : "collège" -> "Coll 3e" (0.75, ✓) ; combinaison p.26 : "Aucun" -> "Aucune" (0.88, ✓) |
| `grossesse.visites[*].date_venue` | 3 | 1 | flou p.3 : "2025-09-28" -> "2025-10-28" (0.75, ✓) ; jpeg p.11 : "2025-12-23" -> "2025-12-13" (0.85) ; jpeg p.11 : "2026-02-22" -> "2026-02-21" (0.85) |
| `antecedents.familiaux.maladies_hereditaires` | 3 | 0 | ombre p.10 : "femme : oncle ; mari : RAS" -> "femme : Oncle ; mari : RAS" (0.85) ; sombre p.10 : "femme : oncle ; mari : RAS" -> "femme : Oncle ; mari : RAS" (0.85) ; jpeg p.10 : "femme : oncle ; mari : RAS" -> "femme : Oncle ; mari : RAS" (0.85) |
| `grossesse.ddr` | 2 | 2 | combinaison p.3 : "2025-04-26" -> "2025-09-26" (0.80, ✓) ; combinaison p.35 : "2025-07-25" -> "2025-07-15" (0.90, ✓) |
| `pp_tardif.mere.tension` | 2 | 0 | flou p.7 : "107/71" -> "107/77" (0.85) ; combinaison p.7 : "107/71" -> "107/79" (0.85) |
| `grossesse.visites[*].age_gestationnel_sa` | 2 | 2 | combinaison p.35 : 16 -> 14 (0.75, ✓) ; combinaison p.43 : 13 -> 15 (0.80, ✓) |
| `grossesse.visites[*].hemoglobine_g_dl` | 1 | 0 | flou p.3 : 11.4 -> 11.9 (0.80) |
| `pp_tardif.nouveau_ne.temperature_c` | 1 | 1 | combinaison p.8 : 36.8 -> 36.5 (0.85, ✓) |
| `pp_precoce.mere.pouls` | 1 | 1 | flou p.13 : 79 -> 74 (0.80, ✓) |
| `grossesse.taille_cm` | 1 | 0 | combinaison p.43 : 164 -> 169 (0.90) |
| `grossesse.tests.glycemie_g_l` | 1 | 1 | combinaison p.43 : 0.76 -> 0.9 (0.75, ✓) |
| `pp_tardif.nouveau_ne.age_jours` | 1 | 0 | combinaison p.48 : 48 -> 42 (0.85) |

## Réflexion du modèle et erreurs

Jetons de réflexion : mesurés (`usage.output_tokens_details.thinking_tokens`) pour les lectures récentes, sinon estimés (sortie totale - JSON de l'outil, 1.81 caractères par jeton calibrés sur 4 lectures mesurées). Surcroît = réflexion dégradée / réflexion de la page propre.

Corrélation de Spearman sur 128 pages : surcroît de réflexion / taux de doutes = +0.56 ; surcroît / taux d'erreurs sans alerte = +0.32.

| Surcroît de réflexion | Pages | Doutes par champ | Erreurs sans alerte par champ |
|---|---:|---:|---:|
| faible (x0.3 à x1.1) | 42 | 1.0% | 0.50% |
| moyen (x1.1 à x2.4) | 43 | 4.4% | 0.47% |
| fort (x2.5 à x11.6) | 43 | 47.8% | 2.41% |

Surcroît médian de réflexion par type de page : ACCOUCHEMENT x2.2, ANTECEDENTS x2.2, GROSSESSE_ACTUELLE x4.9, IDENTIFICATION x1.6, PP_PRECOCE_MERE x1.6, PP_PRECOCE_NOUVEAU_NE x1.0, PP_TARDIF_MERE x1.4, PP_TARDIF_NOUVEAU_NE x2.8.

## Limites

- La référence est l'extraction propre, pas la vérité terrain : ses rares erreurs (1,1 %) comptent ici comme accords.
- Les 5 dégradations simples ne portent que sur les patientes 1 et 2 (16 pages chacune).
- Jetons de réflexion estimés pour les lectures antérieures au suivi : ordre de grandeur, pas mesure exacte.
