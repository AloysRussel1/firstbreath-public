"""Étape 5 – Normalisation des lectures du modèle (règles de shared/CONVENTIONS.md).

normaliser_page(type_page, entree) -> liste de champs
    {champ, valeur, statut, confiance, texte_lu}, valeurs au type du schéma.

Le modèle transcrit ; ce fichier :
- fixe les statuts évidents (vide ou tiret -> NON_FOURNI, « RAS »/« Néant » -> CONNU "RAS", « ? » -> INCONNU) ;
- convertit les valeurs (dates AAAA-MM-JJ, entiers, décimaux, tension "110/70", booléens, choix) ;
- déduit les champs à cases de `cases_a_cocher` et les compare à la valeur lue ;
- passe en A_REVISER tout champ douteux : conversion impossible, hors plage plausible,
  désaccord avec les cases, confiance < seuil_question_suivi ;
- complète les champs du schéma absents de la réponse (A_REVISER, confiance 0) ;
- retire noms, CIN, téléphones et adresses repérés dans `valeur` et `texte_lu`.
"""
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

from extraction.schema_outil import OBJETS, SCHEMA, STATUTS, aplatir

SEUIL = STATUTS["seuil_question_suivi"]
# Signaux de plausibilité : motif attendu -> la confiance est multipliée par le facteur s'il n'est pas
# respecté, sans forcer A_REVISER (le vrai registre des photos 1-*.jpg utilise un autre format de N°).
SIGNAUX = {
    "identification.numero_fiche": (re.compile(r"\d{4}-\d{3}-\d{3}"), 0.85, "format AAAA-NNN-NNN non respecté"),
}
VIDES = {"", "-", "—", "–", "/", ".", "..", "..."}
# Synonymes des choix et des booléens séparés : « O » est un groupe sanguin, pas « oui ».
SYNONYMES = {
    "NEG": "NEGATIF", "NEGATIVE": "NEGATIF",
    "POS": "POSITIF", "POSITIVE": "POSITIF", "+": "POSITIF",
    "H.T.A": "HTA", "H.T.A.": "HTA", "PREECLAMPSIE": "PRE_ECLAMPSIE",
}
BOOLEENS = {
    "OUI": True, "VRAI": True, "TRUE": True, "COCHEE": True, "COCHE": True, "X": True,
    "NON": False, "FAUX": False, "FALSE": False, "NON_COCHEE": False,
}

# ---------- Confidentialité ----------
NOMS = r"[A-ZÀ-Ý][\w'’-]+(?:\s+[A-ZÀ-Ý][\w'’-]+)*"
LIBELLE = r"(?i:\b(?:nom|pr[ée]nom|nom du mari|adresse|t[ée]l[ée]phone|t[ée]l\.?)(?:\s*/\s*pr[ée]nom)?(?:\s+de la parturiente)?)"
MOTIFS_PRIVES = [  # (motif, remplacement) ; le libellé imprimé est conservé
    (re.compile(r"\b0[5-7](?:[ .-]?\d{2}){4}\b"), "[retiré]"),                     # téléphone
    (re.compile(r"\b[A-Z]{1,2}\d{5,6}\b"), "[retiré]"),                             # CIN
    (re.compile(r"(?i)\b\d+\s*,?\s*(?:rue|avenue|av\.|bd|boulevard|lot|lotissement|derb|quartier|r[ée]sidence|imm\.?|immeuble|appt?\.?)\b[^;]*"),
     "[retiré]"),                                                                    # adresse
    (re.compile(rf"\b(Dr|Docteur|Pr|Professeur|Mme|Madame|Mlle|Mademoiselle|Monsieur|M\.)\.?\s+{NOMS}"), r"\1 [nom]"),
    (re.compile(rf"({LIBELLE}\s*:?\s*){NOMS}"), r"\1[nom]"),                         # « Nom/Prénom : X »
    (re.compile(rf"((?i:\b(?:m[èe]re|nouveau-n[ée])\b)\s*[—–-]\s*){NOMS}"), r"\1[nom]"),  # en-têtes PP
]


def retirer_prive(texte):
    """Remplace tout nom, CIN ou téléphone repéré. Renvoie (texte, modifié ?)."""
    if not isinstance(texte, str):
        return texte, False
    nouveau = texte
    for motif, remplacement in MOTIFS_PRIVES:
        nouveau = motif.sub(remplacement, nouveau)
    return nouveau, nouveau != texte


# ---------- Conversions ----------

def cle_texte(texte):
    """« Négatif » -> « NEGATIF » : majuscules sans accents, espaces et tirets en « _ »."""
    t = unicodedata.normalize("NFD", str(texte)).encode("ascii", "ignore").decode()
    return re.sub(r"[\s-]+", "_", t.strip().upper())


RAS = {cle_texte(x) for x in ("RAS", "R.A.S", "R.A.S.", "Néant", "Aucun", "Aucune", "Rien")}
# Listes fermées de valeurs texte : une lecture égale à une entrée, aux accents, à la casse et à la
# ponctuation près, prend l'orthographe officielle (ex. « Hoceima » -> « Hoceïma »).
# Régions du Maroc : découpage officiel de 2015 (12 régions).
CANONIQUES = {
    "identification.region": [
        "Tanger-Tétouan-Al Hoceïma", "L'Oriental", "Fès-Meknès", "Rabat-Salé-Kénitra",
        "Béni Mellal-Khénifra", "Casablanca-Settat", "Marrakech-Safi", "Drâa-Tafilalet",
        "Souss-Massa", "Guelmim-Oued Noun", "Laâyoune-Sakia El Hamra", "Dakhla-Oued Ed-Dahab",
    ],
}


def forme_simple(texte):
    """« Tanger-Tétouan-Al Hoceïma » -> « tangertetouanalhoceima » (comparaison tolérante)."""
    t = unicodedata.normalize("NFD", texte).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", t)


def canonique(cle, valeur):
    for officiel in CANONIQUES.get(cle, []):
        if forme_simple(officiel) == forme_simple(valeur):
            return officiel
    return valeur


# Champs texte où « Aucun » est une vraie valeur (pas « rien à signaler ») : la règle RAS ne s'applique pas.
SANS_REGLE_RAS = {"profil.niveau_instruction"}
INCONNUS = {cle_texte(x) for x in ("?", "??", "inconnu", "inconnue", "ne sait pas", "NSP")}


def en_date(v):
    v = str(v).strip()
    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", v)
    if m:
        a, mo, j = map(int, m.groups())
    else:
        m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})", v)
        if not m:
            raise ValueError
        j, mo, a = map(int, m.groups())
        a += 2000 if a < 100 else 0
    return date(a, mo, j).isoformat()


def en_nombre(v):
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(v))
    if not m:
        raise ValueError
    return float(m.group().replace(",", "."))


def en_entier(v):
    n = en_nombre(v)
    if n != int(n):
        raise ValueError
    return int(n)


def en_tension(v):
    m = re.fullmatch(r"(\d{1,3}(?:[.,]\d)?)\s*/\s*(\d{1,3}(?:[.,]\d)?)", str(v).strip())
    if not m:
        raise ValueError
    sys_, dia = (float(x.replace(",", ".")) for x in m.groups())
    if sys_ < 30:  # notation en cmHg : « 11/7 » -> 110/70
        sys_, dia = sys_ * 10, dia * 10
    return f"{round(sys_)}/{round(dia)}"


def en_booleen(v):
    if isinstance(v, bool):
        return v
    b = BOOLEENS.get(cle_texte(v))
    if b is None:
        raise ValueError
    return b


def en_choix(v, choix):
    c = cle_texte(v)
    c = SYNONYMES.get(c, SYNONYMES.get(str(v).strip().upper(), c))
    if c in choix:
        return c
    debut = [x for x in choix if isinstance(c, str) and c and x.startswith(c)]
    if len(debut) == 1:
        return debut[0]
    raise ValueError


def convertir(d, v):
    """Convertit une valeur lue vers le type du schéma ; ValueError si impossible."""
    t = d["type"]
    if t == "date": return en_date(v)
    if t == "entier": return en_entier(v)
    if t == "decimal": return en_nombre(v)
    if t == "tension": return en_tension(v)
    if t == "booleen": return en_booleen(v)
    if t == "choix": return en_choix(v, d["choix"])
    if t == "liste_choix": return [en_choix(x, d["choix"]) for x in v]
    if t == "liste_objets": return [o for o in (convertir_objet(d["cle"], x) for x in v) if o]
    return re.sub(r"\s+", " ", str(v)).strip()


def convertir_objet(cle, objet):
    """Objet d'un champ liste_objets (CONVENTIONS.md §7) : valeurs normalisées, absence = None.

    Renvoie None si l'objet est entièrement vide ; ValueError si une date ou un nombre est illisible.
    """
    if not isinstance(objet, dict):
        raise ValueError
    sortie = {}
    for k, t in OBJETS[cle].items():
        v, _ = retirer_prive(str(objet.get(k) or "").strip())
        if v in VIDES:
            sortie[k] = None
        elif t == "texte" and cle_texte(v) in RAS:
            sortie[k] = "RAS"
        else:
            sortie[k] = convertir({"type": t}, v)
    return sortie if any(x is not None for x in sortie.values()) else None


def hors_plage(d, v):
    if d["type"] == "tension":
        s, di = map(int, v.split("/"))
        p = SCHEMA["plages_tension"]
        return not (p["systolique"][0] <= s <= p["systolique"][1] and p["diastolique"][0] <= di <= p["diastolique"][1])
    p = d.get("plage_plausible")
    return p is not None and isinstance(v, (int, float)) and not (p[0] <= v <= p[1])


# ---------- Cases à cocher ----------

# Cases « parentes » (options qui ne sont pas des valeurs du schéma) : quand aucune case enfant
# n'est cochée, (option, état) -> valeur ; valeur None = situation incertaine (A_REVISER).
PARENTES = {
    "accouchement.lieu": [("A_DOMICILE", "COCHEE", "DOMICILE_NON_ASSISTE"), ("MILIEU_SURVEILLE", "COCHEE", None)],
    "accouchement.mode": [("VOIE_BASSE_INSTRUMENTALE", "COCHEE", None)],
    "pp_precoce.mere.planification_familiale": [("DESIRE_METHODE", "NON_COCHEE", "AUCUNE"), ("DESIRE_METHODE", "COCHEE", None)],
    "pp_tardif.mere.planification_familiale": [("DESIRE_METHODE", "NON_COCHEE", "AUCUNE"), ("DESIRE_METHODE", "COCHEE", None)],
}


def lire_cases(cle, d, etats):
    """Valeur déduite des cases : (valeur, sûr ?). valeur None si aucune case cochée."""
    if d["type"] == "booleen":
        e = etats.get("case")
        return {"COCHEE": True, "NON_COCHEE": False}.get(e), e != "INCERTAINE"
    # Cases enfants = valeurs du schéma (ou numéros pour un entier) ; les autres sont des parentes.
    enfants = {o: e for o, e in etats.items() if d["type"] == "entier" or o in d.get("choix", [])}
    cochees = [o for o, e in enfants.items() if e == "COCHEE"]
    incertaines = [o for o, e in enfants.items() if e == "INCERTAINE"]
    if d["type"] == "entier":  # ex. VAT 1 à 5 : plus grand numéro coché
        return (max(int(o) for o in cochees) if cochees else None), not incertaines
    if d["type"] == "liste_choix":
        return (cochees or None), not incertaines
    # choix : une seule case attendue
    if len(cochees) == 1 and not incertaines:
        return cochees[0], True
    if not cochees and not incertaines:
        for option, etat, valeur in PARENTES.get(cle, []):
            if etats.get(option) == etat:
                return valeur, valeur is not None
        return None, True
    return (cochees + incertaines)[0], False


# ---------- Un champ ----------

def definition(cle):
    m = re.fullmatch(r"grossesse\.visites\[(\d)\]\.(\w+)", cle)
    for page in SCHEMA["pages"].values():
        if m and "visites" in page:
            return next((c for c in page["visites"]["champs"] if c["cle"] == m.group(2)), None)
        for c in page["champs"]:
            if c["cle"] == cle:
                return c
    return None


def a_reviser(ch, raison):
    ch["statut"] = "A_REVISER"
    ch.setdefault("raisons", []).append(raison)


def normaliser_champ(ch, etats_cases=None):
    d = definition(ch["champ"])
    v, texte = ch.get("valeur"), ch.get("texte_lu") or ""
    try:
        conf = min(max(float(ch.get("confiance")), 0.0), 1.0)
    except (TypeError, ValueError):
        conf = 0.0
    statut = ch.get("statut") if ch.get("statut") in STATUTS["statuts_champ"] else "A_REVISER"
    # confiance_modele : confiance déclarée par le modèle, avant tout ajustement (signal pour confiance.py).
    sortie = {"champ": ch["champ"], "valeur": None, "statut": statut, "confiance": conf,
              "confiance_modele": conf, "plausible": True}

    # Confidentialité : sur la valeur texte et sur le texte lu.
    v, v_modif = retirer_prive(v)
    texte, _ = retirer_prive(texte)
    sortie["texte_lu"] = texte

    # Cases à cocher : lecture case par case, prioritaire, comparée à la valeur du champ.
    if etats_cases:
        v_cases, sur = lire_cases(ch["champ"], d, etats_cases)
        try:
            v_champ = convertir(d, v) if v not in ("", [], None) else None
        except ValueError:
            v_champ = None
        if v_cases is not None:
            v = v_cases
        elif not sur:
            v = v_champ if v_champ is not None else ""  # cases incertaines : meilleure lecture du champ
        else:
            v = ""  # aucune case cochée
            sortie["aucune_case_cochee"] = d["type"] == "liste_choix"
        if not sur:
            a_reviser(sortie, "case incertaine")
        elif v_cases is None and v_champ is not None and d["type"] != "booleen":
            a_reviser(sortie, f"aucune case cochée mais valeur lue ({v_champ})")
        elif v_champ is not None and v_cases is not None and (
                sorted(v_champ) != sorted(v_cases) if d["type"] == "liste_choix" else v_champ != v_cases):
            a_reviser(sortie, f"cases ({v_cases}) et lecture ({v_champ}) en désaccord")

    brut = cle_texte(v) if isinstance(v, str) else None
    # Statuts évidents fixés par le code.
    if brut in INCONNUS:
        sortie["statut"] = "INCONNU"
    elif d["type"] == "texte" and brut in RAS and ch["champ"] not in SANS_REGLE_RAS:
        sortie.update(statut="CONNU", valeur="RAS")
    elif v in ([], None) or (isinstance(v, str) and v.strip() in VIDES):
        if sortie["statut"] in ("CONNU", "A_REVISER") and not sortie.get("raisons"):
            sortie["statut"] = "NON_FOURNI"
    elif sortie["statut"] in ("CONNU", "A_REVISER"):
        try:
            sortie["valeur"] = convertir(d, v)
            if d["type"] == "texte":
                sortie["valeur"] = canonique(ch["champ"], sortie["valeur"])
            if d["type"] in ("entier", "decimal", "tension") and hors_plage(d, sortie["valeur"]):
                sortie["plausible"] = False
                a_reviser(sortie, "hors plage plausible")
        except (ValueError, TypeError):
            sortie["valeur"] = v  # meilleure lecture conservée telle quelle
            a_reviser(sortie, f"format non reconnu pour le type {d['type']}")
    if v_modif:
        a_reviser(sortie, "identifiant personnel retiré de la valeur")

    if sortie["statut"] not in ("CONNU", "A_REVISER"):
        sortie["valeur"] = None
    signal = SIGNAUX.get(ch["champ"])
    if signal and isinstance(sortie["valeur"], str) and not signal[0].fullmatch(sortie["valeur"]):
        sortie["confiance"] = round(sortie["confiance"] * signal[1], 3)
        sortie.setdefault("signaux_format", []).append(f"{signal[2]} (confiance x{signal[1]})")
    if sortie["confiance"] < SEUIL and sortie["statut"] != "A_REVISER":
        a_reviser(sortie, f"confiance {sortie['confiance']:.2f} < {SEUIL}")
    if sortie["statut"] == "A_REVISER" and not sortie.get("raisons"):
        sortie["raisons"] = ["jugé douteux par le modèle"]
    return sortie


# ---------- Une page ----------

def cles_attendues(type_page):
    page = SCHEMA["pages"][type_page]
    cles = [c["cle"] for c in page["champs"]]
    if "visites" in page:
        cles += [f"grossesse.visites[{i}].{c['cle']}"
                 for i in range(len(page["visites"]["index"])) for c in page["visites"]["champs"]]
    return cles


def normaliser_page(type_page, entree):
    cases = entree.get("cases_a_cocher") or {}
    lus = {c["champ"]: c for c in aplatir(type_page, entree)}
    champs = []
    for cle in cles_attendues(type_page):
        if cle in lus:
            etats = cases.get(cle) if isinstance(cases.get(cle), dict) else None
            champs.append(normaliser_champ(lus[cle], etats))
        else:
            champs.append({"champ": cle, "valeur": None, "statut": "A_REVISER", "confiance": 0.0,
                           "confiance_modele": 0.0, "plausible": True,
                           "texte_lu": "", "raisons": ["champ absent de la réponse du modèle"]})
    marquer_visites_non_faites(champs)
    listes_vides_si_consultation(champs)
    return champs


def listes_vides_si_consultation(champs):
    """CONVENTIONS.md §7 : liste de cases sans aucune case cochée, consultation faite -> CONNU [].

    « Consultation faite » = un champ *.date_consultation CONNU sur la page ; sinon NON_FOURNI reste.
    """
    if not any(c["champ"].endswith(".date_consultation") and c["statut"] == "CONNU" for c in champs):
        return
    for c in champs:
        if c.get("aucune_case_cochee") and c["statut"] == "NON_FOURNI":
            c["statut"], c["valeur"] = "CONNU", []
            if c["confiance"] < SEUIL:
                a_reviser(c, f"confiance {c['confiance']:.2f} < {SEUIL}")


def marquer_visites_non_faites(champs):
    """Colonne de visite entièrement vide = visite pas encore faite -> NON_APPLICABLE (CONVENTIONS.md §3)."""
    par_visite = {}
    for c in champs:
        m = re.fullmatch(r"grossesse\.visites\[(\d)\]\..+", c["champ"])
        if m:
            par_visite.setdefault(m.group(1), []).append(c)
    for visite in par_visite.values():
        if all(c["valeur"] is None and c["statut"] in ("NON_FOURNI", "NON_APPLICABLE") for c in visite):
            for c in visite:
                c["statut"] = "NON_APPLICABLE"
