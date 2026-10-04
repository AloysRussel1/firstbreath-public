"""Étape 2 – Index des images de data/Paper Registry/ -> extraction/index.json.

Pour chaque PNG du spécimen : sha256, n° de page n (tiré du nom de fichier),
patiente = (n-1)//8+1, position = (n-1)%8+1, type de page (ordre de shared/statuts.json),
doublon (même sha256 qu'un fichier précédent) et split (dev : patientes 1-6, test : 7-10).
Les vraies photos 1-*.jpg sont listées à part, split "terrain".

Usage (depuis la racine, venv activé) :
    python extraction/index_donnees.py
"""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER = RACINE / "data" / "Paper Registry"
SORTIE = Path(__file__).resolve().parent / "index.json"
TYPES_PAGE = json.loads((RACINE / "shared/statuts.json").read_text(encoding="utf-8"))["types_page"]
NOM_PNG = re.compile(r"^dossiers_specimen_10_patientes-(\d+)(?:__.+)?\.png$")


def sha256(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def relatif(chemin: Path) -> str:
    return chemin.relative_to(RACINE).as_posix()


def indexer_pages():
    pages, premier_par_hash = [], {}
    # Tri par n° de page puis par nom : le fichier sans suffixe passe en premier et devient l'original.
    fichiers = sorted((f for f in DOSSIER.glob("*.png") if NOM_PNG.match(f.name)),
                      key=lambda f: (int(NOM_PNG.match(f.name).group(1)), len(f.name), f.name))
    for f in fichiers:
        n = int(NOM_PNG.match(f.name).group(1))
        h = sha256(f)
        patiente = (n - 1) // 8 + 1
        pages.append({
            "fichier": relatif(f),
            "sha256": h,
            "page_pdf": n,
            "patiente": patiente,
            "position": (n - 1) % 8 + 1,
            "type_page": TYPES_PAGE[(n - 1) % 8],
            "doublon_de": premier_par_hash.get(h),
            "split": "dev" if patiente <= 6 else "test",
        })
        premier_par_hash.setdefault(h, relatif(f))
    return pages


def indexer_photos():
    return [{"fichier": relatif(f), "sha256": sha256(f), "split": "terrain"}
            for f in sorted(DOSSIER.glob("1-*.jpg"))]


def afficher_resume(pages, photos):
    uniques = [p for p in pages if p["doublon_de"] is None]
    print(f"Images PNG        : {len(pages)} ({len(uniques)} uniques, {len(pages) - len(uniques)} doublons)")
    print(f"Pages du PDF      : {len({p['page_pdf'] for p in pages})} / 80")
    variantes = Counter(p["page_pdf"] for p in uniques)
    differentes = sorted(n for n, k in variantes.items() if k > 1)
    print(f"Pages avec plusieurs images différentes (même n°, hash distincts) : {differentes or 'aucune'}")
    print(f"Photos terrain    : {len(photos)}")
    print("\nImages uniques par type de page et par split :")
    print(f"  {'type_page':<24}{'dev':>5}{'test':>6}")
    for t in TYPES_PAGE:
        dev = sum(1 for p in uniques if p["type_page"] == t and p["split"] == "dev")
        test = sum(1 for p in uniques if p["type_page"] == t and p["split"] == "test")
        print(f"  {t:<24}{dev:>5}{test:>6}")
    print(f"  {'TOTAL':<24}{sum(p['split'] == 'dev' for p in uniques):>5}{sum(p['split'] == 'test' for p in uniques):>6}")


def main():
    pages, photos = indexer_pages(), indexer_photos()
    index = {
        "version": 1,
        "description": "Index des images de data/Paper Registry/ (généré par extraction/index_donnees.py)",
        "regles": {"patiente": "(n-1)//8+1", "position": "(n-1)%8+1",
                   "split": {"dev": "patientes 1 à 6", "test": "patientes 7 à 10", "terrain": "photos 1-*.jpg"},
                   "doublon_de": "fichier original de même sha256, null si l'image est l'original"},
        "pages": pages,
        "photos_terrain": photos,
    }
    SORTIE.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Écrit : {relatif(SORTIE)}\n")
    afficher_resume(pages, photos)


if __name__ == "__main__":
    main()
