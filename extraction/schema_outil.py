"""Étape 3 – Format de sortie (tool use) généré depuis shared/schema_champs.json.

outil(type_page) -> définition d'outil à passer dans `tools=[...]` de l'API.
aplatir(type_page, entree) -> liste de champs {champ, valeur, statut, confiance, texte_lu}
    avec les visites converties en clés grossesse.visites[i].champ.
    Les valeurs sont encore brutes (chaînes) : normalisation.py les convertit ensuite.

Chaque champ demandé au modèle a quatre propriétés : valeur, statut, confiance, texte_lu.
Le format ne contient que des clés du schéma : aucun nom, CIN, téléphone, adresse,
ni titre ou en-tête de page (où le nom de la patiente peut figurer).

Usage (affiche le format d'un type de page) :
    python extraction/schema_outil.py IDENTIFICATION
"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((RACINE / "shared/schema_champs.json").read_text(encoding="utf-8"))
STATUTS = json.loads((RACINE / "shared/statuts.json").read_text(encoding="utf-8"))
INTERDITS = STATUTS["champs_interdits"]

FORMAT_TYPE = {
    "texte": "texte",
    "entier": "nombre entier",
    "decimal": "nombre décimal avec un point",
    "date": "date AAAA-MM-JJ",
    "booleen": "OUI si oui ou case cochée, NON si non ou case non cochée",
    "tension": "tension \"SYS/DIA\" en mmHg, ex. \"110/70\"",
    "choix": "une valeur de la liste",
    "liste_choix": "liste de valeurs de la liste",
    "liste_objets": "liste d'objets, un par colonne remplie du tableau",
}

# Clés des objets des champs liste_objets, fixées par shared/CONVENTIONS.md §7 (cle -> type de la valeur).
OBJETS = {
    "obstetrique.accouchements_anterieurs": {
        "date": "date", "modalite": "texte", "indication_cesarienne": "texte",
        "complication": "texte", "poids_g": "entier", "complication_nouveau_ne": "texte",
    },
}


def schema_valeur(d):
    """Schéma JSON de la propriété `valeur` selon le type du champ.

    Le modèle transcrit, normalisation.py convertit (entier, date, booléen…).
    Pas de type nullable : l'API limite les unions de types en mode strict.
    Une valeur absente s'écrit "" (ou [] pour une liste), le statut dit pourquoi.
    """
    t = d["type"]
    if t == "booleen":
        return {"type": "string", "enum": ["OUI", "NON", ""]}
    if t == "choix":
        return {"type": "string", "enum": d["choix"] + [""]}
    if t == "liste_choix":
        return {"type": "array", "items": {"type": "string", "enum": d["choix"]}}
    if t == "liste_objets":
        # Objets aux clés de OBJETS ; chaque valeur est une chaîne ("" si absente), convertie ensuite.
        cles = OBJETS[d["cle"]]
        return {"type": "array", "items": {"type": "object", "properties": {k: {"type": "string"} for k in cles},
                                           "required": list(cles), "additionalProperties": False}}
    return {"type": "string"}  # texte, entier, decimal, date, tension


def description(d):
    texte = f"{d['label_fr']} ({FORMAT_TYPE[d['type']]}"
    if d.get("choix"):
        texte += " : " + ", ".join(d["choix"])
    if d.get("unite"):
        texte += f" ; unité {d['unite']}"
    return texte + ")"


def schema_champ(d):
    return {
        "type": "object",
        "properties": {
            "valeur": schema_valeur(d),
            "statut": {"type": "string", "enum": STATUTS["statuts_champ"]},
            "confiance": {"type": "number", "description": "Confiance dans la lecture, entre 0 et 1."},
            "texte_lu": {"type": "string",
                         "description": "Texte exactement tel qu'écrit sur la page, \"\" si rien n'est écrit."},
        },
        "required": ["valeur", "statut", "confiance", "texte_lu"],
        "additionalProperties": False,
    }


def verifier_confidentialite(cle):
    # Comparaison par segment entier : "nom" ne doit pas bloquer "nouveau_ne.anomalie".
    if any(segment in INTERDITS for segment in cle.split(".")):
        raise ValueError(f"Clé interdite dans le format de sortie : {cle}")


ETATS_CASE = ["COCHEE", "NON_COCHEE", "INCERTAINE"]


def schema_cases(cases):
    """Rubrique `cases_a_cocher` : chaque case de la page lue une par une.

    cases = {cle_du_champ: [options]} ; un booléen a une seule option, "case".
    """
    return {
        "type": "object",
        "description": "État de chaque case à cocher de la page, lue une par une.",
        "properties": {
            cle: {"type": "object",
                  "properties": {o: {"type": "string", "enum": ETATS_CASE} for o in options},
                  "required": list(options), "additionalProperties": False}
            for cle, options in cases.items()
        },
        "required": list(cases), "additionalProperties": False,
    }


def outil(type_page, cases=None, strict=None):
    """Définition de l'outil pour un type de page.

    cases (facultatif) : cases à cocher à lire une par une, voir schema_cases().

    Les champs de même forme partagent un sous-schéma dans $defs (référencé par $ref),
    sinon l'API refuse le mode strict (« compiled grammar is too large »).
    GROSSESSE_ACTUELLE (9 visites x 16 champs) reste trop grand même ainsi : pas de mode
    strict pour cette page, la forme de la réponse est vérifiée en Python.
    """
    page = SCHEMA["pages"][type_page]
    defs = {}

    def ref(d):
        verifier_confidentialite(d["cle"])
        schema = schema_champ(d)
        signature = json.dumps(schema, sort_keys=True)
        nom = defs.setdefault(signature, (f"champ_{len(defs) + 1}", schema))[0]
        return {"$ref": f"#/$defs/{nom}", "description": description(d)}

    proprietes = {d["cle"]: ref(d) for d in page["champs"]}

    if "visites" in page:
        v = page["visites"]
        champs_visite = {"visite": {"type": "string", "enum": v["index"],
                                    "description": "Colonne du tableau des visites."}}
        for d in v["champs"]:
            champs_visite[d["cle"]] = ref(d)
        proprietes["visites"] = {
            "type": "array",
            "description": "Tableau des visites : une entrée par colonne, dans l'ordre "
                           + ", ".join(v["index"]) + ", y compris les colonnes vides.",
            "items": {"type": "object", "properties": champs_visite,
                      "required": list(champs_visite), "additionalProperties": False},
        }

    if cases:
        for cle in cases:
            verifier_confidentialite(cle)
        proprietes["cases_a_cocher"] = schema_cases(cases)

    return {
        "name": f"enregistrer_{type_page.lower()}",
        "description": f"Enregistre les champs lus sur une page {type_page} du registre maternel. "
                       "Ne contient aucun nom, prénom, CIN, téléphone ni adresse.",
        "strict": ("visites" not in page) if strict is None else strict,
        "input_schema": {"type": "object", "properties": proprietes,
                         "required": list(proprietes), "additionalProperties": False,
                         "$defs": {nom: schema for nom, schema in defs.values()}},
    }


PROPRIETES_CHAMP = ("valeur", "statut", "confiance", "texte_lu")


def _champ(cle, lu):
    # Ne garde que les 4 propriétés attendues (GROSSESSE_ACTUELLE n'est pas en mode strict).
    return {"champ": cle, **{p: lu.get(p) for p in PROPRIETES_CHAMP}}


def aplatir(type_page, entree):
    """Convertit l'entrée de l'outil en liste de champs aux clés exactes du schéma.

    Les champs absents ou mal formés sont ignorés ici ; normalisation.py décide quoi en faire.
    """
    page = SCHEMA["pages"][type_page]
    champs = [_champ(d["cle"], entree[d["cle"]]) for d in page["champs"]
              if isinstance(entree.get(d["cle"]), dict)]
    if "visites" in page:
        index = page["visites"]["index"]
        for visite in entree.get("visites") or []:
            if not isinstance(visite, dict) or visite.get("visite") not in index:
                continue
            i = index.index(visite["visite"])
            for d in page["visites"]["champs"]:
                if isinstance(visite.get(d["cle"]), dict):
                    champs.append(_champ(f"grossesse.visites[{i}].{d['cle']}", visite[d["cle"]]))
    return champs


if __name__ == "__main__":
    type_page = sys.argv[1] if len(sys.argv) > 1 else "IDENTIFICATION"
    print(json.dumps(outil(type_page), ensure_ascii=False, indent=1))
