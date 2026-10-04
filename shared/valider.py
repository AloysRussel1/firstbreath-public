"""Validateur commun FirstBreath – tout le monde l'utilise.
Usage : python shared/valider.py chemin/vers/fichier.json
En code : from shared.valider import valider_page, valider_dossier
"""
import json, re, sys
from datetime import date
from pathlib import Path

ICI = Path(__file__).parent
SCHEMA = json.loads((ICI / "schema_champs.json").read_text(encoding="utf-8"))
STATUTS = json.loads((ICI / "statuts.json").read_text(encoding="utf-8"))
VISITE = re.compile(r"^grossesse\.visites\[(\d)\]\.(\w+)$")
TELEPHONE = re.compile(r"\b0[5-7](?:[ .-]?\d{2}){4}\b")
CIN = re.compile(r"\b[A-Z]{1,2}\d{5,6}\b")

CHAMPS = {}
for nom, page in SCHEMA["pages"].items():
    for c in page["champs"]:
        CHAMPS[c["cle"]] = c
    if "visites" in page:
        VISITE_CHAMPS = {c["cle"]: c for c in page["visites"]["champs"]}
        NB_VISITES = len(page["visites"]["index"])

def definition(cle):
    m = VISITE.match(cle)
    if m:
        return VISITE_CHAMPS.get(m.group(2)) if int(m.group(1)) < NB_VISITES else None
    return CHAMPS.get(cle)

def verifier_type(d, v):
    t = d["type"]
    try:
        if t == "entier": ok = isinstance(v, int) and not isinstance(v, bool)
        elif t == "decimal": ok = isinstance(v, (int, float)) and not isinstance(v, bool)
        elif t == "booleen": ok = isinstance(v, bool)
        elif t == "date": date.fromisoformat(v); ok = True
        elif t == "tension": ok = isinstance(v, str) and re.fullmatch(r"\d{2,3}/\d{2,3}", v) is not None
        elif t == "choix": ok = v in d["choix"]
        elif t == "liste_choix": ok = isinstance(v, list) and all(x in d["choix"] for x in v)
        elif t == "liste_objets": ok = isinstance(v, list)
        else: ok = isinstance(v, str)
    except (TypeError, ValueError):
        ok = False
    return ok

def hors_plage(d, v):
    if d["type"] == "tension":
        s, di = map(int, v.split("/"))
        p = SCHEMA["plages_tension"]
        return not (p["systolique"][0] <= s <= p["systolique"][1] and p["diastolique"][0] <= di <= p["diastolique"][1])
    p = d.get("plage_plausible")
    return p is not None and not (p[0] <= v <= p[1])

def valider_champ(ch):
    erreurs, alertes = [], []
    cle, v, st, conf = ch.get("champ"), ch.get("valeur"), ch.get("statut"), ch.get("confiance")
    if cle and any(segment in STATUTS["champs_interdits"] for segment in cle.split(".")):
        return [f"{cle} : champ INTERDIT (identifiant direct)"], []
    d = definition(cle) if cle else None
    if d is None:
        return [f"{cle} : clé absente du schéma"], []
    if st not in STATUTS["statuts_champ"]:
        erreurs.append(f"{cle} : statut invalide '{st}'")
    if not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
        erreurs.append(f"{cle} : confiance doit être entre 0 et 1")
    if st == "CONNU":
        if v is None: erreurs.append(f"{cle} : CONNU mais valeur vide")
        elif not verifier_type(d, v): erreurs.append(f"{cle} : valeur '{v}' ne respecte pas le type {d['type']}")
        elif d["type"] in ("entier", "decimal", "tension") and hors_plage(d, v):
            alertes.append(f"{cle} : valeur {v} hors plage plausible -> devrait être A_REVISER")
    elif st in ("INCONNU", "NON_FOURNI", "ILLISIBLE", "NON_APPLICABLE") and v is not None:
        erreurs.append(f"{cle} : statut {st} mais valeur non vide")
    if isinstance(v, str) and (TELEPHONE.search(v) or CIN.search(v)):
        erreurs.append(f"{cle} : la valeur ressemble à un téléphone ou une CIN")
    return erreurs, alertes

def valider_page(page):
    erreurs, alertes = [], []
    if page.get("type_page") not in STATUTS["types_page"]:
        erreurs.append(f"type_page invalide : {page.get('type_page')}")
    for ch in page.get("champs", []):
        e, a = valider_champ(ch); erreurs += e; alertes += a
    return erreurs, alertes

def valider_dossier(dossier):
    erreurs, alertes = [], []
    if dossier.get("etat") not in STATUTS["etats_enregistrement"] + STATUTS["etats_echec"]:
        erreurs.append(f"etat invalide : {dossier.get('etat')}")
    for p in dossier.get("pages", []):
        e, a = valider_page(p); erreurs += e; alertes += a
    return erreurs, alertes

if __name__ == "__main__":
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    e, a = valider_dossier(data) if "pages" in data else valider_page(data)
    for x in a: print("ALERTE :", x)
    for x in e: print("ERREUR :", x)
    print("VALIDE" if not e else f"INVALIDE ({len(e)} erreur(s))")
    sys.exit(1 if e else 0)
