"""Étape 1 (robustesse) – Versions dégradées des 48 pages de dev, reproductibles.

Pour chaque original du split dev (patientes 1 à 6, doublons exclus), six dégradations :
    flou, rotation (3 à 8 degrés), ombre (partielle), sombre (faible luminosité),
    jpeg (compression forte), combinaison (rotation + ombre + sombre + flou léger + jpeg).
Le hasard est tiré d'une graine fixe par (page, dégradation) : mêmes images à chaque lancement
avec la même version de Pillow (voir README).

Sorties : extraction/degradees/<page>_<degradation>.jpg (ignoré par git)
          extraction/degradees/index_degradees.json (page d'origine, sha256, type, patiente, dégradation)

Usage (depuis la racine, venv activé) :
    python extraction/degrader.py
"""
import hashlib
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

RACINE = Path(__file__).resolve().parent.parent
SORTIE = Path(__file__).resolve().parent / "degradees"
GRAINE = "firstbreath-degradation-v1"
QUALITE = 92  # JPEG des versions dégradées (sauf « jpeg » et « combinaison », très compressées)


def flou(im, r):
    rayon = r.uniform(1.8, 2.6)
    return im.filter(ImageFilter.GaussianBlur(rayon)), {"rayon": round(rayon, 2)}


def rotation(im, r):
    angle = r.uniform(3, 8) * r.choice([-1, 1])
    fond = im.getpixel((5, 5))  # couleur du papier, pour les coins découverts
    return im.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=fond), {"angle": round(angle, 2)}


def ombre(im, r):
    """Ombre portée : dégradé sombre sur une bande d'un bord de la page (main ou téléphone)."""
    w, h = im.size
    bord = r.choice(["gauche", "droite", "haut", "bas"])
    part = r.uniform(0.35, 0.55)
    force = r.uniform(0.45, 0.65)  # opacité maximale de l'ombre
    masque = Image.new("L", im.size, 0)
    d = ImageDraw.Draw(masque)
    longueur = int((w if bord in ("gauche", "droite") else h) * part)
    for i in range(longueur):
        a = int(255 * force * (1 - i / longueur) ** 0.7)
        if bord == "gauche": d.line([(i, 0), (i, h)], fill=a)
        elif bord == "droite": d.line([(w - 1 - i, 0), (w - 1 - i, h)], fill=a)
        elif bord == "haut": d.line([(0, i), (w, i)], fill=a)
        else: d.line([(0, h - 1 - i), (w, h - 1 - i)], fill=a)
    masque = masque.filter(ImageFilter.GaussianBlur(25))
    noir = Image.new("RGB", im.size, (20, 15, 15))
    return Image.composite(noir, im, masque), {"bord": bord, "part": round(part, 2), "force": round(force, 2)}


def sombre(im, r):
    lum = r.uniform(0.38, 0.5)
    contraste = r.uniform(0.7, 0.85)
    im = ImageEnhance.Brightness(im).enhance(lum)
    return ImageEnhance.Contrast(im).enhance(contraste), {"luminosite": round(lum, 2), "contraste": round(contraste, 2)}


def jpeg(im, r):
    return im, {"qualite": r.randint(6, 10)}


def combinaison(im, r):
    params = {}
    for nom, f in (("rotation", rotation), ("ombre", ombre), ("sombre", sombre)):
        im, p = f(im, r)
        params[nom] = p
    im = im.filter(ImageFilter.GaussianBlur(1.0))
    params["flou_rayon"] = 1.0
    params["qualite"] = r.randint(15, 22)
    return im, params


DEGRADATIONS = {"flou": flou, "rotation": rotation, "ombre": ombre, "sombre": sombre,
                "jpeg": jpeg, "combinaison": combinaison}


def main():
    index = json.loads((RACINE / "extraction/index.json").read_text(encoding="utf-8"))
    pages = sorted((p for p in index["pages"] if p["split"] == "dev" and p["doublon_de"] is None),
                   key=lambda p: p["page_pdf"])
    SORTIE.mkdir(exist_ok=True)
    entrees = []
    for p in pages:
        original = Image.open(RACINE / p["fichier"]).convert("RGB")
        for nom, f in DEGRADATIONS.items():
            r = random.Random(f"{GRAINE}|{p['sha256']}|{nom}")  # graine fixe par page et dégradation
            im, params = f(original.copy(), r)
            qualite = params.get("qualite", QUALITE)
            fichier = SORTIE / f"page_{p['page_pdf']:02d}_{nom}.jpg"
            im.save(fichier, format="JPEG", quality=qualite, optimize=False, progressive=False)
            entrees.append({
                "fichier": fichier.relative_to(RACINE).as_posix(),
                "sha256": hashlib.sha256(fichier.read_bytes()).hexdigest(),
                "degradation": nom, "parametres": params,
                "fichier_origine": p["fichier"], "sha256_origine": p["sha256"],
                "page_pdf": p["page_pdf"], "patiente": p["patiente"], "position": p["position"],
                "type_page": p["type_page"], "split": p["split"],
            })
    (SORTIE / "index_degradees.json").write_text(json.dumps({
        "version": 1, "graine": GRAINE, "degradations": list(DEGRADATIONS),
        "description": "Versions dégradées des pages de dev (générées par extraction/degrader.py)",
        "images": entrees,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(entrees)} images dégradées ({len(pages)} pages x {len(DEGRADATIONS)} dégradations) dans {SORTIE.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
