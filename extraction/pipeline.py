"""Tâche 2 – Pipeline d'extraction. Respecter shared/CONTRAT.md.

extract_page(image_path: str) -> {"type_page": ..., "champs": [{champ, valeur, statut, confiance, page_source}]}

extraire(image_path) donne en plus le détail utile au débogage (texte_lu, raisons des A_REVISER,
coût, cache) ; extract_page() n'en garde que les clés du contrat.
"""
import hashlib
import json
from pathlib import Path

from extraction.client import detecter_type_page, lire_page
from extraction.confiance import appliquer_confiance, ratio_reflexion
from extraction.normalisation import normaliser_page
from extraction.prompts import prompt
from extraction.schema_outil import STATUTS, outil

ICI = Path(__file__).resolve().parent
CLES_CONTRAT = ("champ", "valeur", "statut", "confiance", "page_source")
_index = None


def type_page_connu(image_path):
    """Type de page connu d'après le sha256 de l'image, sinon None.

    Sources : extraction/index.json (images de data/) et, s'il existe,
    extraction/degradees/index_degradees.json (versions dégradées générées par degrader.py).
    """
    global _index
    if _index is None:
        index = json.loads((ICI / "index.json").read_text(encoding="utf-8"))
        _index = {p["sha256"]: p["type_page"] for p in index["pages"]}
        degradees = ICI / "degradees" / "index_degradees.json"
        if degradees.exists():
            _index.update({i["sha256"]: i["type_page"]
                           for i in json.loads(degradees.read_text(encoding="utf-8"))["images"]})
    return _index.get(hashlib.sha256(Path(image_path).read_bytes()).hexdigest())


def extraire(image_path, type_page=None, confiance_finale=True):
    """Extraction détaillée d'une page (type : donné, sinon index.json, sinon détection automatique).

    confiance_finale=False : sans la couche de confiance.py (cohérence, réflexion), pour les comparaisons.
    """
    confiance_type = 1.0
    type_page = type_page or type_page_connu(image_path)
    if type_page is None:
        detection = detecter_type_page(image_path)
        type_page, confiance_type = detection["type_page"], detection["confiance"]
    p = prompt(type_page)
    lecture = lire_page(image_path, type_page, p["texte"], p["version"],
                        definition_outil=outil(type_page, p["cases"], p.get("strict")))
    page_source = STATUTS["types_page"].index(type_page) + 1  # n° de la page dans le registre
    champs = [{**c, "page_source": page_source} for c in normaliser_page(type_page, lecture["entree"])]
    ratio = ratio_reflexion(type_page, lecture)
    if confiance_finale:
        appliquer_confiance(type_page, champs, ratio)
    return {"type_page": type_page, "confiance_type": confiance_type, "champs": champs, "version_prompt": p["version"],
            "modele": lecture["modele"], "effort": lecture.get("effort"), "ratio_reflexion": ratio,
            "jetons_reflexion": lecture.get("jetons_reflexion"),  # None pour les lectures antérieures à ce suivi
            "image_sha256": lecture["image_sha256"],
            "cout_usd": lecture["cout_usd"] + lecture.get("cout_essais_tronques", 0.0),
            "duree_s": lecture["duree_s"], "depuis_cache": lecture["depuis_cache"]}


def extract_page(image_path: str) -> dict:
    """Format de shared/CONTRAT.md. Lève client.EchecTraitement (attribut etat = "ECHEC_TRAITEMENT")
    si le modèle n'a rendu aucune lecture complète malgré les nouveaux essais."""
    page = extraire(image_path)
    return {"type_page": page["type_page"],
            "champs": [{k: c[k] for k in CLES_CONTRAT} for c in page["champs"]]}
