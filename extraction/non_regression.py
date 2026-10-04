"""Non-régression : repasse toutes les lectures en cache dans la normalisation actuelle.

Aucun appel API. Vérifie que chaque page passe toujours shared/valider.py.
À lancer après chaque modification de normalisation.py (ou de schema_outil.py) :
    python extraction/non_regression.py
Code de sortie 1 si au moins une page est invalide.
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from extraction.confiance import appliquer_confiance, ratio_reflexion
from extraction.normalisation import normaliser_page
from extraction.pipeline import CLES_CONTRAT
from extraction.schema_outil import STATUTS
from shared.valider import valider_page

CACHE = Path(__file__).resolve().parent / "cache"


def main():
    fichiers = sorted(CACHE.glob("*.json"))
    statuts, invalides, pages = Counter(), [], 0
    for f in fichiers:
        lecture = json.loads(f.read_text(encoding="utf-8"))
        type_page = lecture.get("type_page")
        if type_page not in STATUTS["types_page"] or lecture.get("echec"):
            continue  # détection du type de page, ou essai tronqué : pas une lecture de champs
        pages += 1
        page_source = STATUTS["types_page"].index(type_page) + 1
        try:
            normalises = appliquer_confiance(type_page, normaliser_page(type_page, lecture["entree"]),
                                             ratio_reflexion(type_page, lecture))
            champs = [{**{k: c[k] for k in CLES_CONTRAT if k != "page_source"}, "page_source": page_source}
                      for c in normalises]
            erreurs, _ = valider_page({"type_page": type_page, "champs": champs})
        except Exception as e:  # une exception est aussi une régression
            champs, erreurs = [], [f"exception : {e!r}"]
        statuts.update(c["statut"] for c in champs)
        if erreurs:
            invalides.append((f.name[:12], type_page, lecture.get("version_prompt"), erreurs[:3]))

    print(f"Lectures en cache repassées : {pages}")
    print("Champs par statut :", dict(sorted(statuts.items())))
    for nom, type_page, version, erreurs in invalides:
        print(f"INVALIDE {nom} {type_page} ({version}) : {erreurs}")
    print("NON-RÉGRESSION OK" if not invalides else f"ÉCHEC : {len(invalides)} page(s) invalide(s)")
    sys.exit(1 if invalides else 0)


if __name__ == "__main__":
    main()
