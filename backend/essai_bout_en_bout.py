"""Essai de bout en bout contre un serveur lancé (démo) : envoi d'une page, suivi de l'état, dossier final.

Usage (serveur déjà lancé depuis la racine : uvicorn backend.main:app --port 8000) :
    python backend/essai_bout_en_bout.py
    python backend/essai_bout_en_bout.py "data/Paper Registry/dossiers_specimen_10_patientes-03.png" --page 3
Ne contient aucune clé ; le mode (simule ou anthropic) est celui du serveur.
"""
import argparse
import sys
import time
import uuid
from pathlib import Path

import httpx

RACINE = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", nargs="?", default="data/Paper Registry/dossiers_specimen_10_patientes-01.png")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--sage-femme", default="sf_demo")
    args = parser.parse_args()
    chemin = RACINE / args.image

    with httpx.Client(base_url=args.url, timeout=30) as api:
        print("santé :", api.get("/sante").json())
        envoi = api.post("/captures", files={"image": (chemin.name, chemin.read_bytes(), "image/png" if chemin.suffix == ".png" else "image/jpeg")},
                         data={"session_id": f"demo-{uuid.uuid4().hex[:8]}", "page_no": str(args.page),
                               "sage_femme_id": args.sage_femme}).json()
        capture_id = envoi["capture_id"]
        print(f"capture {capture_id} : {envoi.get('etat_capture')}")

        debut = time.monotonic()
        traiter = api.post(f"/captures/{capture_id}/traiter").json()
        print(f"/traiter a répondu en {time.monotonic() - debut:.2f} s : {traiter['etat']} "
              f"(durée estimée {traiter['duree_estimee_s']} s)")
        while True:
            etat = api.get(f"/captures/{capture_id}/etat").json()
            print(f"  {etat['ecoule_s']} s : {etat['etat']} ({etat['progression']:.0%})")
            if etat["termine"]:
                break
            time.sleep(1)

        info = api.get(f"/captures/{capture_id}").json()
        dossier = api.get(f"/dossiers/{info['dossier_id']}").json()
        champs = [c for p in dossier["pages"] for c in p["champs"]]
        print(f"\ncapture : état {info['etat']}, type {info['type_page']}, sha256 {info['image_sha256'][:12]}…, "
              f"sage-femme {info['sage_femme_id']}, date {info['date_capture']}")
        print(f"dossier {dossier['dossier_id']} : état {dossier['etat']}, {len(dossier['pages'])} page(s), {len(champs)} champs")
        statuts = {}
        for c in champs:
            statuts[c["statut"]] = statuts.get(c["statut"], 0) + 1
        print("statuts :", statuts)
        image = api.get(f"/captures/{capture_id}/image", headers={"X-Role": "SAGE_FEMME", "X-Sage-Femme-Id": args.sage_femme})
        autre = api.get(f"/captures/{capture_id}/image", headers={"X-Role": "SAGE_FEMME", "X-Sage-Femme-Id": "autre"})
        print(f"image d'origine : {image.status_code} pour la sage-femme de la capture "
              f"({'identique' if image.content == chemin.read_bytes() else 'DIFFÉRENTE'}), {autre.status_code} pour une autre")
        return 0 if etat["etat"] in ("TRAITE_IA", "A_REVISER") else 1


if __name__ == "__main__":
    sys.exit(main())
