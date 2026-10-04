"""Étape 4 – Confiance finale de chaque champ.

    confiance_finale = confiance × f_plausible × f_coherent × f_reflexion

- confiance   : confiance du modèle après normalisation (signal de format du N° de fiche compris) ;
- f_plausible : 0,5 si la valeur est hors de la plage plausible du schéma, sinon 1 ;
- f_coherent  : 0,5 si une règle de cohérence entre champs échoue, sinon 1 (le champ passe alors en A_REVISER) ;
- f_reflexion : 1 tant que la page a demandé au plus RATIO_TOLERE fois plus de réflexion qu'une page
                propre du même type, puis diminue de PENTE_REFLEXION par unité de ratio, sans descendre
                sous PLANCHER_REFLEXION.
Un champ CONNU dont la confiance finale passe sous seuil_question_suivi (shared/statuts.json) passe en
A_REVISER. Les champs vides (NON_FOURNI, NON_APPLICABLE…) gardent leur statut : le signal de
réflexion porte sur les valeurs lues, pas sur les cases vides.
Formule volontairement simple : la calibration fine est faite par evaluation/.

Règles de cohérence (CONVENTIONS.md : jamais deviner, signaler le doute) :
- GROSSESSE_ACTUELLE, pour chaque visite : âge gestationnel = (date de venue - DDR) / 7, à ±2 SA ;
  si au moins la moitié des visites comparables (et au moins 2) sont incohérentes, c'est la DDR qui est suspecte ;
- GROSSESSE_ACTUELLE : dates de venue croissantes d'une visite à l'autre, dates de rendez-vous croissantes,
  et rendez-vous postérieur à la venue de la même visite (c'est la date du prochain rendez-vous) ;
- GROSSESSE_ACTUELLE : date prévue d'accouchement = DDR + 280 jours, à ±7 jours ;
- ANTECEDENTS : parité <= gestité.
"""
import json
import re
from datetime import date
from pathlib import Path

from extraction.normalisation import SEUIL, a_reviser

ICI = Path(__file__).resolve().parent
REFERENCE = ICI / "reference_reflexion.json"
TOLERANCE_SA = 2
TOLERANCE_DPA_JOURS = 7
RATIO_TOLERE = 3.0
PENTE_REFLEXION = 0.08
PLANCHER_REFLEXION = 0.6
VISITE = re.compile(r"grossesse\.visites\[(\d)\]\.(\w+)")


# ---------- Signal de réflexion ----------

def charger_reference():
    """Réflexion médiane d'une page propre par type (générée par extraction/sorties.py depuis le cache)."""
    if REFERENCE.exists():
        return json.loads(REFERENCE.read_text(encoding="utf-8"))
    return None


def jetons_reflexion(lecture, cars_par_jeton):
    """Mesurés (usage.output_tokens_details.thinking_tokens) si disponibles, sinon estimés :
    sortie totale - taille du JSON de l'outil / caractères par jeton."""
    if lecture.get("jetons_reflexion") is not None:
        return lecture["jetons_reflexion"]
    if not lecture.get("entree") or not cars_par_jeton:
        return None
    return max(0, round(lecture["jetons_sortie"] - len(json.dumps(lecture["entree"], ensure_ascii=False)) / cars_par_jeton))


def ratio_reflexion(type_page, lecture, reference=None):
    reference = reference or charger_reference()
    if not reference or not reference["par_type"].get(type_page):
        return None
    jetons = jetons_reflexion(lecture, reference["cars_par_jeton"])
    return None if jetons is None else round(jetons / reference["par_type"][type_page], 2)


def facteur_reflexion(ratio):
    if ratio is None or ratio <= RATIO_TOLERE:
        return 1.0
    return max(PLANCHER_REFLEXION, 1 - PENTE_REFLEXION * (ratio - RATIO_TOLERE))


# ---------- Cohérence entre champs ----------

def _date(c):
    if c and c["statut"] in ("CONNU", "A_REVISER") and isinstance(c["valeur"], str):
        try:
            return date.fromisoformat(c["valeur"])
        except ValueError:
            return None
    return None


def _nombre(c):
    if c and c["statut"] in ("CONNU", "A_REVISER") and isinstance(c["valeur"], (int, float)) and not isinstance(c["valeur"], bool):
        return c["valeur"]
    return None


def incoherences(type_page, champs):
    """{clé du champ: [raisons lisibles]} pour les règles de cohérence qui échouent."""
    par_cle = {c["champ"]: c for c in champs}
    raisons = {}

    def signaler(cles, raison):
        for cle in cles:
            raisons.setdefault(cle, []).append(raison)

    if type_page == "GROSSESSE_ACTUELLE":
        ddr = _date(par_cle.get("grossesse.ddr"))
        visites = {}
        for c in champs:
            m = VISITE.fullmatch(c["champ"])
            if m:
                visites.setdefault(int(m.group(1)), {})[m.group(2)] = c
        cle_v = lambda i, nom: f"grossesse.visites[{i}].{nom}"

        # Âge gestationnel et DDR.
        if ddr:
            ecarts = []
            for i, v in sorted(visites.items()):
                venue, sa = _date(v.get("date_venue")), _nombre(v.get("age_gestationnel_sa"))
                if venue and sa is not None:
                    attendu = (venue - ddr).days / 7
                    ecarts.append((i, sa, attendu, abs(sa - attendu) > TOLERANCE_SA))
            faux = [e for e in ecarts if e[3]]
            if len(faux) >= 2 and len(faux) * 2 >= len(ecarts):
                signaler(["grossesse.ddr"], f"DDR incohérente avec l'âge gestationnel de {len(faux)} visites sur {len(ecarts)}")
            else:
                for i, sa, attendu, _ in faux:
                    signaler([cle_v(i, "age_gestationnel_sa"), cle_v(i, "date_venue")],
                             f"âge gestationnel {sa} SA, mais (venue - DDR) / 7 = {attendu:.1f} SA")

        # Ordre chronologique.
        for nom, libelle in (("date_venue", "venue"), ("date_rdv", "rendez-vous")):
            precedent = None
            for i in sorted(visites):
                d = _date(visites[i].get(nom))
                if d is None:
                    continue
                if precedent and d <= precedent[1]:
                    signaler([cle_v(precedent[0], nom), cle_v(i, nom)],
                             f"dates de {libelle} hors de l'ordre chronologique ({precedent[1]} puis {d})")
                precedent = (i, d)
        for i, v in sorted(visites.items()):
            venue, rdv = _date(v.get("date_venue")), _date(v.get("date_rdv"))
            if venue and rdv and rdv <= venue:
                signaler([cle_v(i, "date_venue"), cle_v(i, "date_rdv")],
                         f"prochain rendez-vous ({rdv}) pas après la venue ({venue})")

        # Date prévue d'accouchement.
        dpa = _date(par_cle.get("grossesse.date_prevue_accouchement"))
        if ddr and dpa:
            ecart = (dpa - ddr).days - 280
            if abs(ecart) > TOLERANCE_DPA_JOURS:
                signaler(["grossesse.date_prevue_accouchement", "grossesse.ddr"],
                         f"date prévue d'accouchement = DDR + {280 + ecart} jours (attendu 280 ± {TOLERANCE_DPA_JOURS})")

    if type_page == "ANTECEDENTS":
        gestite, parite = _nombre(par_cle.get("obstetrique.gestite")), _nombre(par_cle.get("obstetrique.parite"))
        if gestite is not None and parite is not None and parite > gestite:
            signaler(["obstetrique.parite", "obstetrique.gestite"], f"parité {parite} supérieure à la gestité {gestite}")
    return raisons


# ---------- Confiance finale ----------

def appliquer_confiance(type_page, champs, ratio=None):
    """Ajoute à chaque champ la confiance finale et ses signaux ; met à jour statut et raisons."""
    incoherents = incoherences(type_page, champs)
    f_r = facteur_reflexion(ratio)
    for c in champs:
        coherent = c["champ"] not in incoherents
        for raison in incoherents.get(c["champ"], []):
            a_reviser(c, raison)
        f_p = 1.0 if c.get("plausible", True) else 0.5
        f_c = 1.0 if coherent else 0.5
        finale = round(c["confiance"] * f_p * f_c * f_r, 3)
        if c["statut"] == "CONNU" and finale < SEUIL:
            a_reviser(c, f"confiance finale {finale:.2f} < {SEUIL}"
                         + (f" (réflexion x{ratio:.1f} par rapport à une page propre)" if f_r < 1 else ""))
        c["signaux"] = {
            "confiance_modele": c.get("confiance_modele", c["confiance"]),
            "plausible": c.get("plausible", True),
            "coherent": coherent,
            "ratio_reflexion": ratio,
            "raison": " ; ".join(c.get("raisons", []) + c.get("signaux_format", [])) or None,
        }
        c["confiance"] = finale
    return champs
