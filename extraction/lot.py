"""Extraction d'un lot de pages et résumé.

Usage (depuis la racine, venv activé) :
    python extraction/lot.py                                  # pages propres du split dev (48 pages)
    python extraction/lot.py --degradation combinaison        # versions dégradées (voir degrader.py)
    python extraction/lot.py --degradation flou rotation --patientes 1 2
    python extraction/lot.py --split test --autoriser-test    # évaluation finale seulement
Les pages déjà en cache ne coûtent rien.

Pour les images dégradées, « accord avec la page propre » = part des champs dont la valeur et le
statut sont identiques à l'extraction de la page d'origine (mesure de robustesse sans vérité terrain).
"""
import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from extraction import client
from extraction.pipeline import CLES_CONTRAT, extraire
from shared.valider import valider_page

RACINE = Path(__file__).resolve().parent.parent
INDEX_DEGRADEES = RACINE / "extraction/degradees/index_degradees.json"


def selection(args):
    """Liste de (variante, chemin, entrée d'index de la page d'origine)."""
    index = json.loads((RACINE / "extraction/index.json").read_text(encoding="utf-8"))
    originaux = {p["fichier"]: p for p in index["pages"] if p["doublon_de"] is None}
    if not args.degradation:
        return [("propre", RACINE / p["fichier"], p) for p in sorted(originaux.values(), key=lambda p: p["page_pdf"])
                if p["split"] == args.split and (not args.patientes or p["patiente"] in args.patientes)]
    if not INDEX_DEGRADEES.exists():
        sys.exit("Images dégradées absentes : lancer d'abord python extraction/degrader.py")
    images = json.loads(INDEX_DEGRADEES.read_text(encoding="utf-8"))["images"]
    return [(i["degradation"], RACINE / i["fichier"], originaux[i["fichier_origine"]])
            for i in sorted(images, key=lambda i: (i["degradation"], i["page_pdf"]))
            if ("toutes" in args.degradation or i["degradation"] in args.degradation)
            and (not args.patientes or i["patiente"] in args.patientes)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev", choices=["dev", "test"])
    parser.add_argument("--autoriser-test", action="store_true")
    parser.add_argument("--degradation", nargs="+", help="noms de dégradations, ou « toutes »")
    parser.add_argument("--patientes", nargs="+", type=int)
    parser.add_argument("--cache-seulement", action="store_true", help="aucun appel API")
    args = parser.parse_args()
    client.CACHE_SEULEMENT = args.cache_seulement
    if args.split == "test" and not args.autoriser_test:
        sys.exit("Split test (patientes 7 à 10) : réservé à l'évaluation finale (--autoriser-test).")

    pages = selection(args)
    if any(p["split"] == "test" for _, _, p in pages) and not args.autoriser_test:
        sys.exit("La sélection contient des pages du split test : refusé.")
    debut = time.perf_counter()
    par_variante = defaultdict(lambda: {"pages": 0, "valides": 0, "statuts": Counter(), "accord": 0, "compares": 0,
                                        "cout": 0.0, "duree": 0.0, "appels": 0, "a_reviser": Counter(),
                                        "ecarts": Counter(), "efforts": Counter(), "echecs": 0})
    erreurs = []
    for variante, chemin, origine in pages:
        v = par_variante[variante]
        try:
            page = extraire(chemin)
        except Exception as e:
            v["echecs"] += 1
            erreurs.append((chemin.name, repr(e)))
            continue
        v["efforts"][page.get("effort") or "défaut"] += 1
        contrat = {"type_page": page["type_page"], "champs": [{k: c[k] for k in CLES_CONTRAT} for c in page["champs"]]}
        e, _ = valider_page(contrat)
        v["pages"] += 1
        v["valides"] += not e
        if e:
            erreurs.append((chemin.name, e[:3]))
        v["statuts"].update(c["statut"] for c in page["champs"])
        v["a_reviser"].update(page["type_page"] for c in page["champs"] if c["statut"] == "A_REVISER")
        if not page["depuis_cache"]:
            v["cout"] += page["cout_usd"]
            v["duree"] += page["duree_s"]
            v["appels"] += 1
        if variante != "propre":
            propre = {c["champ"]: c for c in extraire(RACINE / origine["fichier"])["champs"]}
            for c in page["champs"]:
                p = propre[c["champ"]]
                v["compares"] += 1
                if (c["valeur"], c["statut"]) == (p["valeur"], p["statut"]):
                    v["accord"] += 1
                elif c["statut"] == "A_REVISER":
                    v["ecarts"]["doute signalé"] += 1
                elif c["statut"] == p["statut"] == "CONNU":
                    v["ecarts"]["valeur fausse sans alerte"] += 1
                else:
                    v["ecarts"]["autre statut sans alerte"] += 1

    print(f"\n===== Lot : {len(pages)} pages =====")
    print(f"{'variante':<12}{'pages':>6}{'valides':>8}{'champs':>8}{'A_REV':>7}{'accord/propre':>15}{'appels':>8}{'coût $':>8}{'temps s':>9}")
    for nom, v in sorted(par_variante.items()):
        accord = f"{v['accord'] / v['compares']:.1%}" if v["compares"] else "—"
        print(f"{nom:<12}{v['pages']:>6}{v['valides']:>8}{sum(v['statuts'].values()):>8}{v['statuts']['A_REVISER']:>7}"
              f"{accord:>15}{v['appels']:>8}{v['cout']:>8.2f}{v['duree']:>9.0f}")
    total = Counter()
    for v in par_variante.values():
        total.update(v["statuts"])
    print("\nChamps par statut (toutes variantes) :", dict(sorted(total.items())))
    for nom, v in sorted(par_variante.items()):
        if v["a_reviser"]:
            print(f"A_REVISER par type de page — {nom} : {dict(v['a_reviser'].most_common())}")
    print("\nÉcarts avec la page propre (un doute signalé est le bon comportement ; une valeur fausse sans alerte est dangereuse) :")
    for nom, v in sorted(par_variante.items()):
        if v["compares"]:
            print(f"   {nom:<12} " + " | ".join(f"{k} {n} ({n / v['compares']:.1%})" for k, n in v["ecarts"].most_common())
                  + f" | effort : {dict(v['efforts'])} | échecs : {v['echecs']}")
    print(f"\nCe lancement : {sum(v['cout'] for v in par_variante.values()):.2f} $ d'appels, "
          f"{time.perf_counter() - debut:.0f} s au total")
    cumul = sum(json.loads(f.read_text(encoding="utf-8")).get("cout_usd", 0)
                for f in (RACINE / "extraction/cache").glob("*.json"))
    print(f"Coût cumulé de tout le cache (tous essais compris) : {cumul:.2f} $")
    for f, e in erreurs:
        print("ERREUR", f, e)


if __name__ == "__main__":
    main()
