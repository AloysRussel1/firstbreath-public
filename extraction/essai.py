"""Étape 5 – Extrait une ou plusieurs pages, affiche le résultat et le vérifie avec shared/valider.py.

Usage (depuis la racine, venv activé) :
    python extraction/essai.py "data/Paper Registry/dossiers_specimen_10_patientes-01.png"
    python extraction/essai.py --type IDENTIFICATION --patientes 1 2 3
Plusieurs pages du même type sont affichées côte à côte. Patientes 1 à 6 uniquement (dev).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from extraction.pipeline import CLES_CONTRAT, extraire
from shared.valider import valider_page

RACINE = Path(__file__).resolve().parent.parent
INDEX = json.loads((RACINE / "extraction/index.json").read_text(encoding="utf-8"))
COURT = {"CONNU": "", "A_REVISER": "À RÉVISER ", "NON_FOURNI": "non fourni", "INCONNU": "inconnu",
         "ILLISIBLE": "illisible", "NON_APPLICABLE": "sans objet"}


def images_demandees(args):
    if args.images:
        return [Path(i) for i in args.images]
    pages = [p for p in INDEX["pages"] if p["type_page"] == args.type
             and p["patiente"] in args.patientes and p["doublon_de"] is None]
    return [RACINE / p["fichier"] for p in sorted(pages, key=lambda p: p["patiente"])]


def verifier_dev(image):
    sha_split = {p["fichier"]: p["split"] for p in INDEX["pages"]}
    rel = image.resolve().relative_to(RACINE).as_posix() if image.is_absolute() else image.as_posix()
    if sha_split.get(rel) == "test":
        sys.exit(f"Refusé : {image.name} appartient aux patientes 7 à 10 (split test).")


def cellule(c):
    v = c["valeur"]
    texte = "—" if v is None else ("oui" if v is True else "non" if v is False else
                                   ", ".join(v) if isinstance(v, list) else str(v))
    if c["statut"] not in ("CONNU", "A_REVISER"):
        texte = COURT[c["statut"]]
    elif c["statut"] == "A_REVISER":
        texte = "⚠ " + texte
    return f"{texte} ({c['confiance']:.2f})"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("images", nargs="*")
    parser.add_argument("--type", default="IDENTIFICATION")
    parser.add_argument("--patientes", nargs="+", type=int, default=[1])
    args = parser.parse_args()
    if any(n > 6 for n in args.patientes) and not args.images:
        sys.exit("Patientes 1 à 6 uniquement pendant le développement.")

    images = images_demandees(args)
    pages = []
    for image in images:
        verifier_dev(image)
        pages.append(extraire(image))

    # Tableau côte à côte
    noms = [i.name.replace("dossiers_specimen_10_patientes-", "p.").replace(".png", "") for i in images]
    largeur = 30
    print(f"\n{'champ':<38}" + "".join(f"{n:<{largeur}}" for n in noms))
    print("-" * (38 + largeur * len(noms)))
    for i, c in enumerate(pages[0]["champs"]):
        print(f"{c['champ']:<38}" + "".join(f"{cellule(p['champs'][i]):<{largeur}}" for p in pages))

    # Raisons des A_REVISER, textes lus, validation
    for nom, page in zip(noms, pages):
        print(f"\n== {nom} · {page['type_page']} · prompt {page['version_prompt']} · {page['modele']} · "
              f"{'cache' if page['depuis_cache'] else f'{page['cout_usd']:.4f} $, {page['duree_s']:.1f} s'}")
        for c in page["champs"]:
            if c.get("raisons") or c.get("signaux_format"):
                print(f"   ⚠ {c['champ']} : {' ; '.join(c.get('raisons', []) + c.get('signaux_format', []))}")
        contrat = {"type_page": page["type_page"], "champs": [{k: c[k] for k in CLES_CONTRAT} for c in page["champs"]]}
        erreurs, alertes = valider_page(contrat)
        for a in alertes:
            print("   ALERTE :", a)
        print("   valider.py :", "VALIDE" if not erreurs else f"INVALIDE {erreurs}")


if __name__ == "__main__":
    main()
