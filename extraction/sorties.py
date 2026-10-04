"""Sorties détaillées par page, en lisant uniquement le cache (aucun appel API).

1. extraction/reference_reflexion.json : réflexion médiane d'une page propre par type de page (pages de
   dev), et nombre de caractères par jeton du JSON de l'outil (calibré sur les lectures où la réflexion
   est mesurée), pour estimer la réflexion des lectures antérieures à son suivi.
2. extraction/sorties/<variante>/page_<NN>.json, variante = propre ou nom de la dégradation :
   pour chaque champ, champ, valeur, statut, confiance finale et signaux
   (confiance_modele, plausible, coherent, ratio_reflexion, raison).
   Fichiers versionnés : evaluation/ s'en sert pour la calibration.

Usage (depuis la racine, venv activé) :
    python extraction/sorties.py
"""
import contextlib
import io
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from extraction import client
from extraction.confiance import REFERENCE
from extraction.pipeline import extraire
from extraction.prompts import prompt

RACINE = Path(__file__).resolve().parent.parent
SORTIES = RACINE / "extraction/sorties"


def lectures_cache():
    return [json.loads(f.read_text(encoding="utf-8")) for f in (RACINE / "extraction/cache").glob("*.json")]


def ecrire_reference(index, cache):
    mesurees = [r for r in cache if r.get("jetons_reflexion") is not None and not r.get("echec")
                and r["type_page"] != "DETECTION" and r.get("entree")]
    cars_par_jeton = (sum(len(json.dumps(r["entree"], ensure_ascii=False)) for r in mesurees)
                      / sum(r["jetons_sortie"] - r["jetons_reflexion"] for r in mesurees))
    par_sha = defaultdict(list)
    for r in cache:
        par_sha[(r["image_sha256"], r["type_page"])].append(r)
    reflexion = defaultdict(list)
    for p in index["pages"]:
        if p["split"] != "dev" or p["doublon_de"] is not None:
            continue
        version = prompt(p["type_page"])["version"]
        lecture = next((r for r in par_sha[(p["sha256"], p["type_page"])]
                        if r["version_prompt"] == version and not r.get("echec") and r.get("entree")), None)
        if lecture:
            j = lecture.get("jetons_reflexion")
            if j is None:
                j = max(0, round(lecture["jetons_sortie"] - len(json.dumps(lecture["entree"], ensure_ascii=False)) / cars_par_jeton))
            reflexion[p["type_page"]].append(j)
    reference = {
        "description": "Réflexion médiane d'une page propre (dev) par type ; généré par extraction/sorties.py",
        "cars_par_jeton": round(cars_par_jeton, 3),
        "lectures_mesurees": len(mesurees),
        "par_type": {t: max(1, round(statistics.median(v))) for t, v in sorted(reflexion.items())},
        "pages_par_type": {t: len(v) for t, v in sorted(reflexion.items())},
    }
    REFERENCE.write_text(json.dumps(reference, ensure_ascii=False, indent=1), encoding="utf-8")
    return reference


def ecrire_page(variante, page_pdf, patiente, page):
    dossier = SORTIES / variante
    dossier.mkdir(parents=True, exist_ok=True)
    contenu = {
        "variante": variante, "page_pdf": page_pdf, "patiente": patiente, "type_page": page["type_page"],
        "image_sha256": page["image_sha256"], "modele": page["modele"], "effort": page["effort"],
        "version_prompt": page["version_prompt"], "ratio_reflexion": page["ratio_reflexion"],
        "champs": [{"champ": c["champ"], "valeur": c["valeur"], "statut": c["statut"], "confiance": c["confiance"],
                    "signaux": c["signaux"]} for c in page["champs"]],
    }
    (dossier / f"page_{page_pdf:02d}.json").write_text(json.dumps(contenu, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    client.CACHE_SEULEMENT = True
    index = json.loads((RACINE / "extraction/index.json").read_text(encoding="utf-8"))
    reference = ecrire_reference(index, lectures_cache())
    print(f"Référence de réflexion : {reference['par_type']} ({reference['cars_par_jeton']} caractères/jeton, "
          f"{reference['lectures_mesurees']} lectures mesurées)")

    a_faire = [("propre", RACINE / p["fichier"], p["page_pdf"], p["patiente"])
               for p in index["pages"] if p["split"] == "dev" and p["doublon_de"] is None]
    degradees = RACINE / "extraction/degradees/index_degradees.json"
    if degradees.exists():
        a_faire += [(i["degradation"], RACINE / i["fichier"], i["page_pdf"], i["patiente"])
                    for i in json.loads(degradees.read_text(encoding="utf-8"))["images"]
                    if i["degradation"] == "combinaison" or i["patiente"] in (1, 2)]
    ecrites, absentes = defaultdict(int), []
    for variante, chemin, page_pdf, patiente in a_faire:
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                page = extraire(chemin)
            except Exception:
                absentes.append(f"{variante}/page_{page_pdf:02d}")
                continue
        ecrire_page(variante, page_pdf, patiente, page)
        ecrites[variante] += 1
    print("Fichiers écrits par variante :", dict(ecrites), f"(total {sum(ecrites.values())})")
    if absentes:
        print("Absentes du cache :", absentes)


if __name__ == "__main__":
    main()
