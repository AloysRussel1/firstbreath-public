"""Étape 5 – Prompts par type de page (avec version, incluse dans la clé du cache).

prompt(type_page) -> {"version": str, "texte": str, "cases": dict | None}
    texte : règles communes (shared/CONVENTIONS.md) + mise en page de ce type de page.
    cases : cases à cocher à lire une par une (voir schema_outil.schema_cases).

Changer un texte de prompt => changer sa version, sinon le cache resservira l'ancienne lecture.
Les types de page sans prompt dédié utilisent le prompt générique (règles communes seules).
"""

REGLES_COMMUNES = """\
Tu transcris une page d'un registre maternel papier marocain (document synthétique, données fictives).
Tu lis et tu recopies ; tu ne déduis rien, tu ne complètes rien, tu ne devines jamais.
Tu réponds uniquement en appelant l'outil fourni, une seule fois, avec tous les champs.

CONFIDENTIALITÉ (absolu) :
- Ne recopie JAMAIS un nom, un prénom, un nom de mari, une CIN, un numéro de téléphone ou une adresse,
  ni dans `valeur`, ni dans `texte_lu`, même s'ils figurent sur la page.
- Cela vaut aussi pour les titres et en-têtes de page (ex. « MÈRE — <nom> ») et pour le personnel
  (« Dr X », « Mme Y ») : remplace le nom par [nom] dans `texte_lu`.
- Ignore le cadre « SPÉCIMEN — DONNÉES FICTIVES / Patiente fictive n°… » en haut à droite.

POUR CHAQUE CHAMP :
- `texte_lu` : uniquement ce qui est écrit pour ce champ, tel quel (sans le libellé imprimé) ;
  "" si rien n'est écrit. Pour un champ à cases, écris le libellé des cases cochées.
- `valeur` : ta lecture dans le format demandé par la description du champ ; "" si pas de valeur.
- `statut` :
  CONNU          valeur lisible et cohérente (« RAS », « Néant », « Aucun » écrits => CONNU, valeur "RAS")
  NON_FOURNI     case vide, tiret « — », ligne vide : valeur ""
  INCONNU        il est écrit « inconnu », « ? », « ne sait pas » : valeur ""
  ILLISIBLE      quelque chose est écrit mais impossible à lire : valeur ""
  NON_APPLICABLE sans objet (ex. types de risque quand la grossesse n'est pas à risque) : valeur ""
  A_REVISER      lu mais douteux (écriture ambiguë, rature, valeur surprenante) : ta meilleure lecture
- `confiance` : probabilité (0 à 1) que ta lecture soit exacte. Sois honnête : en dessous de 0.75,
  le champ sera vérifié par la sage-femme. Mieux vaut signaler un doute que se tromper.

FORMATS : date AAAA-MM-JJ (papier 03/02/2026 -> 2026-02-03) ; décimal avec un point (58,8 -> 58.8) ;
tension "SYS/DIA" en mmHg (« 11/7 » -> "110/70") ; choix : la valeur exacte de la liste
(« Neg » -> NEGATIF) ; booléen : OUI / NON.

CASES À COCHER (rubrique `cases_a_cocher` quand elle existe) : regarde chaque case une par une,
indépendamment des autres : COCHEE (croix, coche ou case noircie), NON_COCHEE (case vide),
INCERTAINE (trace ambiguë, rature, case abîmée). Ne déduis pas l'état d'une case de celui des autres.
"""

IDENTIFICATION = """\
MISE EN PAGE — page IDENTIFICATION (« FICHE DE SURVEILLANCE DE LA GROSSESSE ET DU POST-PARTUM »),
de haut en bas :
1. « N° de la fiche : » suivi d'une ligne manuscrite -> identification.numero_fiche.
   Champ essentiel : recopie chaque caractère (chiffres et tirets) exactement, sans reformater.
2. Une ligne avec deux zones : à gauche « Région : » -> identification.region ;
   à droite « Province : » -> identification.province.
3. « Nom de l'établissement sanitaire : » -> identification.etablissement (nom d'un lieu, pas d'une personne).
4. « Type de l'établissement sanitaire : » puis 5 cases, sur deux lignes :
   DR, CSC, CSU (1re ligne) ; CSCA, CSUA (2e ligne). La case est à droite de son libellé.
   -> identification.type_etablissement (une seule case attendue).
5. Deux cases « Fixe » et « Mobile » (case à gauche du libellé) -> identification.mode_couverture.
6. « Nom/Prénom de la parturiente : » : identifiant direct. NE LE LIS PAS, ne le recopie nulle part.
   Aucun champ ne lui correspond.
7. Encadré en bas :
   - case à gauche de « Grossesse classée à risque : » -> identification.grossesse_a_risque
     (cochée -> OUI, statut CONNU ; non cochée -> NON, statut CONNU).
   - « Si grossesse à risque, préciser le type de risque : » puis 8 cases en deux colonnes,
     case à gauche du libellé : Anémie, H.T.A, Diabète, Cardiopathie (gauche) ;
     Métrorragie, Infection, Pré-éclampsie, Eclampsie (droite) ;
     et « Autres à préciser : ...... » (si du texte y est écrit, ajoute AUTRE).
     -> identification.types_risque : liste des risques cochés.
     Si la grossesse n'est pas classée à risque et qu'aucune case n'est cochée : NON_APPLICABLE.
"""

CASES_IDENTIFICATION = {
    "identification.type_etablissement": ["DR", "CSC", "CSU", "CSCA", "CSUA"],
    "identification.mode_couverture": ["FIXE", "MOBILE"],
    "identification.grossesse_a_risque": ["case"],
    "identification.types_risque": ["ANEMIE", "HTA", "DIABETE", "CARDIOPATHIE", "METRORRAGIE",
                                    "INFECTION", "PRE_ECLAMPSIE", "ECLAMPSIE"],
}

GROSSESSE_ACTUELLE = """\
MISE EN PAGE — page GROSSESSE_ACTUELLE (titre « GROSSESSE ACTUELLE ») :

A. EN-TÊTE (deux lignes au-dessus du tableau) -> champs de page :
   « DDR : » -> grossesse.ddr ; « Taille : » -> grossesse.taille_cm (ex. « 155 cm » -> 155) ;
   « Groupage : » cases A, B, O, AB -> grossesse.groupage ; cases Rh-, Rh+ -> grossesse.rhesus
   (Rh- -> NEGATIF, Rh+ -> POSITIF ; la case est à gauche de son libellé) ;
   « DATE PRÉVUE D'ACCOUCHEMENT : » -> grossesse.date_prevue_accouchement ;
   « DATE DE DÉPASSEMENT DE TERME : » -> grossesse.date_depassement_terme.

B. TABLEAU DES VISITES : 9 colonnes de visites après la colonne des libellés, dans cet ordre :
   1er trimestre Visite 1, 2, 3 -> T1_V1, T1_V2, T1_V3 ;
   2ème trimestre Visite 1, 2, 3 -> T2_V1, T2_V2, T2_V3 ;
   3ème trimestre 7ème, 8ème, 9ème mois -> MOIS_7, MOIS_8, MOIS_9.
   LIS LE TABLEAU COLONNE PAR COLONNE : pour chaque colonne, descends ligne par ligne en restant
   dans la colonne (suis les traits verticaux, ne glisse pas vers la colonne voisine).
   Rends les 9 colonnes dans `visites`, même vides.
   COLONNE ENTIÈREMENT VIDE = visite pas encore faite : tous ses champs NON_APPLICABLE, valeur "".
   Dans une colonne remplie : case vide ou tiret « – » -> NON_FOURNI.
   Lignes du tableau, de haut en bas, et champ de chaque visite :
     Rendez-vous -> date_rdv ; Venue le -> date_venue ; Visites de relance -> relance (Oui/Non) ;
     Age probable -> age_gestationnel_sa (« 12 SA » -> 12) ;
     [EXAMEN CLINIQUE] Poids (kg) -> poids_kg ; TA -> tension ; Anomalies squelette (ignorer) ;
     État des conjonctives (ignorer) ; Examen des seins (ignorer) ; Œdèmes -> oedemes (Oui/Non) ;
     Mouvements actifs -> mouvements_actifs (Oui/Non) ; HU (cm) -> hauteur_uterine_cm ; BCF -> bcf ;
     Examen au spéculum (ignorer) ; TV : état du col -> col (texte, ex. « Fermé ») ;
     TV : présentation -> presentation ; TV : bassin (ignorer) ;
     [EXAMEN BIOLOGIQUE] Glucosurie -> glucosurie ; Albuminurie -> albuminurie ;
     Hémoglobine -> hemoglobine_g_dl (« 11.8 g/dL » -> 11.8) ;
     [EXAMEN FAIT PAR] Examen fait par -> examine_par_fonction : garde UNIQUEMENT la fonction
     (« Dr … » ou médecin -> MEDECIN ; « Sage-femme », « SF » -> SAGE_FEMME ; « Inf. … », infirmier(e)
     -> INFIRMIER). Ne recopie jamais le nom : texte_lu = « Dr [nom] », « Inf. [nom] », « Sage-femme ».

C. EXAMENS BIOLOGIQUES DE PAGE : ces lignes sont dans le tableau, mais ce sont des champs de page
   (une seule valeur pour la grossesse) : prends la valeur écrite, quelle que soit la colonne ;
   si des valeurs différentes figurent dans plusieurs colonnes, mets A_REVISER.
     Rubéole -> grossesse.tests.rubeole ; Toxoplasmose -> grossesse.tests.toxoplasmose ;
     Syphilis (TPHA/VDRL) -> grossesse.tests.syphilis ; Ag HBs -> grossesse.tests.hepatite_b ;
     Sérologie VIH -> grossesse.tests.vih ;
     Plaquettes -> grossesse.tests.plaquettes en milliers par mm3 (« 186k » ou « 186 000 » -> 186) ;
     Bilan glycémique -> grossesse.tests.glycemie_g_l (« 0.93 g/L » -> 0.93) ;
     RAI (si Rh négatif) -> grossesse.tests.rai.
   Il n'y a pas de ligne « Hépatite C » sur ce modèle : grossesse.tests.hepatite_c = NON_FOURNI.

D. TRAITEMENT : ligne « Fer » du tableau -> grossesse.traitement.fer (champ de page) :
   OUI si « Oui » est écrit dans au moins une colonne ; NON si seul « Non » est écrit ;
   NON_FOURNI si la ligne est vide.
"""

CASES_GROSSESSE = {
    "grossesse.groupage": ["A", "B", "O", "AB"],
    "grossesse.rhesus": ["NEGATIF", "POSITIF"],
}

ANTECEDENTS = """\
MISE EN PAGE — page ANTECEDENTS (titre « IDENTIFICATION ET ANTÉCÉDENTS »).
CETTE PAGE CONTIENT LE PLUS D'IDENTIFIANTS DIRECTS : vigilance maximale.

A. CADRE DU HAUT, deux colonnes :
   à gauche : « Age : » -> profil.age (entier) ; « Niveau d'instruction : » -> profil.niveau_instruction ;
              « Adresse : » et « Nom du Mari : » -> INTERDITS, ne pas lire, ne pas recopier ;
   à droite : « CIN : », « Téléphone : » -> INTERDITS, ne pas lire, ne pas recopier ;
              les deux « Profession : » -> aucun champ, ignorer.
   en bas du cadre : case « Consanguinité » -> profil.consanguinite ;
                     case « Grossesse désirée » -> profil.grossesse_desiree
   (case unique : cochée -> OUI, non cochée -> NON, statut CONNU dans les deux cas).
   Aucun de ces identifiants ne doit apparaître dans un `texte_lu`, même partiellement.

B. « ANTÉCÉDENTS HÉRÉDITAIRES ET FAMILIAUX » (tableau à gauche) : lignes HTA, Diabète,
   Maladies héréditaires, Malformations, Allergie(s) ; colonnes « Famille de la femme » et « Mari/famille ».
   -> antecedents.familiaux.hta / diabete / maladies_hereditaires / malformations / allergies.
   Un seul champ pour les deux colonnes :
   - si les deux colonnes disent RAS (ou Néant, Aucun) : valeur "RAS" ;
   - sinon : "femme : <colonne 1> ; mari : <colonne 2>" (ex. "femme : Père ; mari : RAS") ;
   - si les deux sont vides : NON_FOURNI.

C. « ANTÉCÉDENTS DE LA FEMME » (tableau à droite), trois colonnes :
   Médicaux -> antecedents.femme.medicaux ; Chirurgicaux -> antecedents.femme.chirurgicaux ;
   Gynécologiques -> antecedents.femme.gynecologiques (texte de la colonne, « Aucun » -> RAS).

D. « ANTÉCÉDENTS OBSTÉTRICAUX — Anomalies des grossesses antérieures » : lignes Avortement,
   Accouchement prématuré, Mort fœtale in utéro, Autres ; colonne « Nombre » :
   -> obstetrique.avortements / prematures / morts_foetales (entier de la colonne Nombre ;
   case Nombre vide -> NON_FOURNI). Les colonnes Date, Lieu, Age gestationnel n'ont pas de champ.

E. « DÉROULEMENT DES ACCOUCHEMENTS ANTÉRIEURS » : colonnes Accouch. 1 à 5 ; lignes Date,
   Modalité d'extraction, Si césarienne : indication, Complication (type), Poids nouveau-né(s),
   Compl. nouveau-né (type).
   -> obstetrique.accouchements_anterieurs : un objet par colonne REMPLIE, dans l'ordre, avec :
   date (ligne Date, AAAA-MM-JJ) ; modalite (Modalité d'extraction, tel qu'écrit, ex. « Voie basse ») ;
   indication_cesarienne (Si césarienne : indication) ; complication (Complication (type)) ;
   poids_g (Poids nouveau-né(s), nombre seul : « 3626 g » -> "3626") ;
   complication_nouveau_ne (Compl. nouveau-né (type)). Case vide -> "".
   Aucune colonne remplie -> liste vide et NON_FOURNI (NON_APPLICABLE si la parité vaut 0).

F. BAS DE PAGE :
   « Gestation : » -> obstetrique.gestite ; « Parité : » -> obstetrique.parite ;
   « Nombre d'enfants vivants : » -> obstetrique.enfants_vivants ;
   « VAT : » cases 1 2 3 4 5 -> vaccination.vat_doses = plus grand numéro coché (aucune case -> NON_FOURNI) ;
   case « Vaccinée contre la rubéole » -> vaccination.rubeole ;
   case « Vaccinée contre l'hépatite B » -> vaccination.hepatite_b
   (case unique : cochée -> OUI, non cochée -> NON ; les dates « Le » n'ont pas de champ) ;
   « Frottis cervical / IVA (moins de 3 ans) : » -> depistage.frottis_iva.
"""

CASES_ANTECEDENTS = {
    "profil.consanguinite": ["case"],
    "profil.grossesse_desiree": ["case"],
    "vaccination.vat_doses": ["1", "2", "3", "4", "5"],
    "vaccination.rubeole": ["case"],
    "vaccination.hepatite_b": ["case"],
}

ACCOUCHEMENT = """\
MISE EN PAGE — page ACCOUCHEMENT (titre « DÉROULEMENT DE L'ACCOUCHEMENT »).
« Patiente : » suivi d'un nom : identifiant direct, NE LE LIS PAS, ne le recopie nulle part.
Toutes les cases : lis-les une par une dans `cases_a_cocher`, la case est à gauche de son libellé.

A. « Lieu » -> accouchement.lieu :
   case « En milieu surveillé » (MILIEU_SURVEILLE), puis dans l'encadré à droite :
   « Maison d'accouchement » (MAISON_ACCOUCHEMENT), « Maternité » (MATERNITE),
   « Clinique privée » (CLINIQUE_PRIVEE), « Autres : ...... » ;
   case « A domicile » (A_DOMICILE), puis dans l'encadré à droite : « Assisté par un personnel
   qualifié » (DOMICILE_ASSISTE), « Autres : ...... ».
   AUTRE = COCHEE si du texte est écrit sur l'une des lignes « Autres ».
   Valeur : MAISON_ACCOUCHEMENT, MATERNITE, CLINIQUE_PRIVEE, DOMICILE_ASSISTE ;
   à domicile sans « Assisté » coché -> DOMICILE_NON_ASSISTE ; texte sur une ligne « Autres » -> AUTRE.
B. « Date de l'accouchement : » -> accouchement.date.
C. « Mode de l'accouchement : » -> accouchement.mode :
   « Voie basse non instrumentale » (VOIE_BASSE) ; « Voie basse instrumentale » (VOIE_BASSE_INSTRUMENTALE)
   avec en dessous « Forceps » (VOIE_BASSE_INSTRUMENTALE_FORCEPS), « Ventouse »
   (VOIE_BASSE_INSTRUMENTALE_VENTOUSE) ; « Césarienne : Programmée » (CESARIENNE_PROGRAMMEE) ;
   « Urgence » (CESARIENNE_URGENCE, case à droite sur la même ligne).
   Case « Avec épisiotomie » -> accouchement.episiotomie (cochée -> OUI, non cochée -> NON).
   « Préciser l'indication : » -> accouchement.indication_cesarienne
   (pas de césarienne -> NON_APPLICABLE ; césarienne sans indication écrite -> NON_FOURNI).
D. « Présence de complications » : case à droite du titre (PRESENCE), puis « Au moment de
   l'accouchement » et « Suites de couches » (pas de champ), puis « Type de complications » :
   Pré-éclampsie (PRE_ECLAMPSIE), Eclampsie (ECLAMPSIE), Hémorragie (HEMORRAGIE),
   Infection (INFECTION), Autres (AUTRE) -> accouchement.complications : liste des types cochés ;
   aucune complication (PRESENCE non cochée et aucun type coché) -> NON_APPLICABLE.
E. « Etat du nouveau-né : » cases Vivant (VIVANT), Mort-né (MORT_NE), Décès < 24 heures
   (DECES_MOINS_24H) -> nouveau_ne.etat ;
   « Sexe : » -> nouveau_ne.sexe (F ou M) ; « Poids à la naissance : » -> nouveau_ne.poids_naissance_g
   (« 3587 g » -> 3587) ; « Périmètre crânien à la naissance : » -> nouveau_ne.perimetre_cranien_cm ;
   « Anomalie à préciser : » -> nouveau_ne.anomalie (« Aucune » -> RAS) ;
   « Âge gestationnel : » -> nouveau_ne.age_gestationnel_sa (« 40 SA » -> 40).
"""

CASES_ACCOUCHEMENT = {
    "accouchement.lieu": ["MILIEU_SURVEILLE", "MAISON_ACCOUCHEMENT", "MATERNITE", "CLINIQUE_PRIVEE",
                          "A_DOMICILE", "DOMICILE_ASSISTE", "AUTRE"],
    "accouchement.mode": ["VOIE_BASSE", "VOIE_BASSE_INSTRUMENTALE", "VOIE_BASSE_INSTRUMENTALE_FORCEPS",
                          "VOIE_BASSE_INSTRUMENTALE_VENTOUSE", "CESARIENNE_PROGRAMMEE", "CESARIENNE_URGENCE"],
    "accouchement.episiotomie": ["case"],
    "accouchement.complications": ["PRESENCE", "PRE_ECLAMPSIE", "ECLAMPSIE", "HEMORRAGIE", "INFECTION", "AUTRE"],
    "nouveau_ne.etat": ["VIVANT", "MORT_NE", "DECES_MOINS_24H"],
}

PP_MERE = """\
MISE EN PAGE — page post-partum MÈRE (titre « CONSULTATION DU POST-PARTUM PRÉCOCE » ou « TARDIF »,
sous-titre « MÈRE — <nom> » : le nom est un identifiant direct, ne le recopie nulle part).
Les clés de cette page commencent par {p}.mere.

A. Haut de page : deux cases de délai depuis l'accouchement (pas de champ, ignorer) ;
   « Date de la consultation : » -> {p}.mere.date_consultation.
B. « Etat général : » sur une ligne : « T° » -> {p}.mere.temperature_c ; « TA » -> {p}.mere.tension ;
   « Pouls » -> {p}.mere.pouls ; « Poids » -> {p}.mere.poids_kg (« 66 kg » -> 66).
C. « Etat des conjonctives : » cases Normales (NORMALES), Décolorées (DECOLOREES) -> {p}.mere.conjonctives.
D. Globe utérin, lochies, périnée, sphincters, césarienne, seins, mollets, médicaments :
   pas de champ, ignorer.
E. « Présence de complication : » case à droite (PRESENCE), puis Hémorragie (HEMORRAGIE),
   Infection (INFECTION), Eclampsie (ECLAMPSIE), Phlébite (PHLEBITE) en colonne gauche ;
   Complications mammaires (COMPLICATIONS_MAMMAIRES), Anémie (ANEMIE), Autres (AUTRE) en colonne droite
   -> {p}.mere.complications : liste des cochées ; aucune (PRESENCE non cochée, rien coché) -> NON_APPLICABLE.
F. « CONDUITE À TENIR » : « Traitement prescrit : » cases Fer (FER), Vitamine A (VITAMINE_A) ;
   AUTRE = COCHEE si du texte est écrit sur « Autres à préciser » -> {p}.mere.traitement ;
   « Prochain rendez-vous le » -> {p}.mere.prochain_rdv.
G. « PLANIFICATION FAMILIALE » : case « Désire utiliser une méthode » (DESIRE_METHODE) ;
   « Si oui, laquelle : » cases pilule (PILULE), DIU (DIU) ; AUTRE = COCHEE si du texte est écrit sur
   « Autre à préciser » -> {p}.mere.planification_familiale (PILULE, DIU ou AUTRE ;
   « Désire utiliser une méthode » non cochée et aucune méthode -> AUCUNE).
   « Prescription faite », « Référée », « Pourquoi ? » : pas de champ.
"""

PP_NOUVEAU_NE = """\
MISE EN PAGE — page post-partum NOUVEAU-NÉ (titre « CONSULTATION DU POST-PARTUM PRÉCOCE » ou
« TARDIF », sous-titre « NOUVEAU-NÉ »). Les clés de cette page commencent par {p}.nouveau_ne.

A. « Date de la consultation : » -> {p}.nouveau_ne.date_consultation.
B. Cadre principal : « Age » -> {p}.nouveau_ne.age_jours (« 7 jours » -> 7) ;
   « Température » -> {p}.nouveau_ne.temperature_c ; « Poids » -> {p}.nouveau_ne.poids_g (« 3485 g » -> 3485) ;
   « Taille » -> {p}.nouveau_ne.taille_cm ; « Périmètre crânien » -> {p}.nouveau_ne.perimetre_cranien_cm.
   Cases « Nouveau-né prématuré », « Nouveau-né hypotrophe » : pas de champ.
C. « Allaitement : » cases exclusivement au sein (EXCLUSIF), Artificiel (ARTIFICIEL), mixte (MIXTE)
   -> {p}.nouveau_ne.allaitement.
D. « Signes d'une affection grave : » 11 cases sur trois lignes :
   Convulsions (CONVULSIONS), Refus de téter (REFUS_TETER), Hématémèses (HEMATEMESES), Mélaenas (MELAENAS) ;
   Diarrhée (DIARRHEE), Ictère (ICTERE), Tirage sous costal (TIRAGE), Toux (TOUX) ;
   Rythme respiratoire anormal (RYTHME_RESP_ANORMAL), Fièvre (FIEVRE), Hypothermie (HYPOTHERMIE) ;
   AUTRE = COCHEE si « Autres à préciser » (juste en dessous) contient autre chose que Néant/RAS/rien
   -> {p}.nouveau_ne.signes_danger : liste des cochées.
E. Contusions et malformations, évaluation de l'allaitement, vitamine D, complications et
   malformations, « Vu par » (nom du personnel : NE LE RECOPIE PAS), « Décision prise »,
   « Traitement prescrit » : pas de champ, ignorer.
F. « Etat vaccinal » : « Vaccins administrés ce jour : » cases BCG (BCG), HB (HB)
   -> {p}.nouveau_ne.vaccins_du_jour.
G. Case « Transfert » -> {p}.nouveau_ne.transfert (cochée -> OUI, non cochée -> NON).
H. « Revenir pour une visite de suivi nécessaire le » -> {p}.nouveau_ne.prochaine_visite.
"""


def cases_pp_mere(p):
    return {
        f"{p}.mere.conjonctives": ["NORMALES", "DECOLOREES"],
        f"{p}.mere.complications": ["PRESENCE", "HEMORRAGIE", "INFECTION", "ECLAMPSIE", "PHLEBITE",
                                    "COMPLICATIONS_MAMMAIRES", "ANEMIE", "AUTRE"],
        f"{p}.mere.traitement": ["FER", "VITAMINE_A", "AUTRE"],
        f"{p}.mere.planification_familiale": ["DESIRE_METHODE", "PILULE", "DIU", "AUTRE"],
    }


def cases_pp_nouveau_ne(p):
    return {
        f"{p}.nouveau_ne.allaitement": ["EXCLUSIF", "ARTIFICIEL", "MIXTE"],
        f"{p}.nouveau_ne.signes_danger": ["CONVULSIONS", "REFUS_TETER", "HEMATEMESES", "MELAENAS", "DIARRHEE",
                                          "ICTERE", "TIRAGE", "TOUX", "RYTHME_RESP_ANORMAL", "FIEVRE",
                                          "HYPOTHERMIE", "AUTRE"],
        f"{p}.nouveau_ne.vaccins_du_jour": ["BCG", "HB"],
        f"{p}.nouveau_ne.transfert": ["case"],
    }


PROMPTS = {
    "IDENTIFICATION": {"version": "identification-v1", "texte": REGLES_COMMUNES + "\n" + IDENTIFICATION,
                       "cases": CASES_IDENTIFICATION},
    "GROSSESSE_ACTUELLE": {"version": "grossesse-v1", "texte": REGLES_COMMUNES + "\n" + GROSSESSE_ACTUELLE,
                           "cases": CASES_GROSSESSE},
    "ANTECEDENTS": {"version": "antecedents-v2", "texte": REGLES_COMMUNES + "\n" + ANTECEDENTS,
                    "cases": CASES_ANTECEDENTS},
    # Trop de cases pour le mode strict (« compiled grammar is too large ») : forme vérifiée en Python.
    "ACCOUCHEMENT": {"version": "accouchement-v1", "texte": REGLES_COMMUNES + "\n" + ACCOUCHEMENT,
                     "cases": CASES_ACCOUCHEMENT, "strict": False},
}
for _type, _p in [("PP_PRECOCE", "pp_precoce"), ("PP_TARDIF", "pp_tardif")]:
    PROMPTS[f"{_type}_MERE"] = {"version": "pp-mere-v1", "cases": cases_pp_mere(_p),
                                "texte": REGLES_COMMUNES + "\n" + PP_MERE.format(p=_p)}
    PROMPTS[f"{_type}_NOUVEAU_NE"] = {"version": "pp-nouveau-ne-v1", "cases": cases_pp_nouveau_ne(_p),
                                      "texte": REGLES_COMMUNES + "\n" + PP_NOUVEAU_NE.format(p=_p)}

# Détection du type de page (appel léger, haut de page seulement).
DETECTION = {"version": "detection-v1", "texte": """\
Tu vois le haut d'une page d'un registre maternel (document synthétique). Lis le titre et le sous-titre
et choisis le type de page :
- « FICHE DE SURVEILLANCE DE LA GROSSESSE ET DU POST-PARTUM » -> IDENTIFICATION
- « IDENTIFICATION ET ANTÉCÉDENTS » -> ANTECEDENTS
- « GROSSESSE ACTUELLE » -> GROSSESSE_ACTUELLE
- « DÉROULEMENT DE L'ACCOUCHEMENT » -> ACCOUCHEMENT
- « CONSULTATION DU POST-PARTUM PRÉCOCE » + « MÈRE » -> PP_PRECOCE_MERE ; + « NOUVEAU-NÉ » -> PP_PRECOCE_NOUVEAU_NE
- « CONSULTATION DU POST-PARTUM TARDIF » + « MÈRE » -> PP_TARDIF_MERE ; + « NOUVEAU-NÉ » -> PP_TARDIF_NOUVEAU_NE
Si le titre est absent, illisible ou différent, donne ta meilleure hypothèse avec une confiance basse.
Ne recopie aucun nom. Réponds uniquement en appelant l'outil."""}
GENERIQUE = {"version": "generique-v1",
             "texte": REGLES_COMMUNES + "\nLis chaque champ de l'outil à l'endroit où son libellé figure sur la page.",
             "cases": None}


def prompt(type_page):
    return PROMPTS.get(type_page, GENERIQUE)
