"""Étape 1 – Premier appel au modèle de vision sur une image de data/.

Usage (depuis la racine, venv activé) :
    python extraction/essai_api.py
    python extraction/essai_api.py "data/Paper Registry/dossiers_specimen_10_patientes-03.png"
"""
import base64
import os
import re
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

RACINE = Path(__file__).resolve().parent.parent
MODELE = "claude-sonnet-5"
IMAGE_PAR_DEFAUT = RACINE / "data/Paper Registry/dossiers_specimen_10_patientes-01.png"
TYPES_MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}

load_dotenv(RACINE / ".env")


def verifier_dev(chemin: Path):
    """Refuse les pages des patientes 7 à 10 (réservées au test final)."""
    m = re.search(r"dossiers_specimen_10_patientes-(\d+)(?:__.+)?\.png$", chemin.name)
    if m and (int(m.group(1)) - 1) // 8 + 1 >= 7:
        sys.exit(f"Refusé : {chemin.name} appartient aux patientes 7 à 10 (split test).")


def main():
    chemin = Path(sys.argv[1]) if len(sys.argv) > 1 else IMAGE_PAR_DEFAUT
    if not chemin.is_absolute():
        chemin = RACINE / chemin
    verifier_dev(chemin)
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY absente : crée le fichier .env à la racine (voir GUIDE_EQUIPE.md).")

    image = base64.standard_b64encode(chemin.read_bytes()).decode("utf-8")
    client = anthropic.Anthropic()  # lit ANTHROPIC_API_KEY chargée depuis .env
    reponse = client.messages.create(
        model=MODELE,
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": TYPES_MEDIA[chemin.suffix.lower()],
                                             "data": image}},
                {"type": "text", "text": "Cette image est une page d'un registre maternel (données synthétiques). "
                                         "Indique le titre de la page et le N° de la fiche, puis liste les "
                                         "rubriques visibles. Ne recopie aucun nom, CIN, téléphone ni adresse."},
            ],
        }],
    )

    if reponse.stop_reason == "refusal":
        sys.exit("Le modèle a refusé la requête.")
    print(f"Image  : {chemin.relative_to(RACINE)}")
    print(f"Modèle : {reponse.model}")
    print(f"Jetons : {reponse.usage.input_tokens} en entrée, {reponse.usage.output_tokens} en sortie\n")
    print("".join(b.text for b in reponse.content if b.type == "text"))


if __name__ == "__main__":
    try:
        main()
    except anthropic.AuthenticationError:
        sys.exit("Clé refusée : vérifie ANTHROPIC_API_KEY dans le fichier .env à la racine.")
    except anthropic.APIConnectionError:
        sys.exit("Pas de connexion à l'API Anthropic.")
