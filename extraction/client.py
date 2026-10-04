"""Étape 4 – Seul fichier qui parle au modèle.

lire_page(image_path, type_page, prompt, version_prompt, modele=None) -> dict
    Envoie l'image et l'outil du type de page, renvoie l'entrée de l'outil remplie par le modèle.
    Cache disque dans extraction/cache/ : clé = sha256(image) + type de page + version du prompt + modèle.
    Affiche le coût et le temps de chaque appel.

Configuration (fichier .env à la racine, facultatif) :
    EXTRACTION_FOURNISSEUR = anthropic (défaut) | simule (aucun appel réseau, tout NON_FOURNI)
    EXTRACTION_MODELE      = claude-sonnet-5 (défaut)
    EXTRACTION_MODELE_DETECTION = claude-haiku-4-5 (défaut ; détection du type de page)

Usage (test : deux appels identiques, le second doit venir du cache) :
    python extraction/client.py
"""
import base64
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from extraction.schema_outil import outil

RACINE = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / "cache"
load_dotenv(RACINE / ".env")

FOURNISSEUR = os.getenv("EXTRACTION_FOURNISSEUR", "anthropic")
MODELE_DEFAUT = os.getenv("EXTRACTION_MODELE", "claude-sonnet-5")
MODELE_DETECTION = os.getenv("EXTRACTION_MODELE_DETECTION", "claude-haiku-4-5")
ESSAIS_MAX = 2
MAX_JETONS_SORTIE = 32000
TYPES_MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
# Prix en dollars par million de jetons (entrée, sortie).
PRIX = {
    "claude-sonnet-5": (2.00, 10.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


class ErreurLecture(Exception):
    """Le modèle n'a pas rendu de lecture exploitable (refus, sortie tronquée, pas d'outil)."""


class EchecTraitement(ErreurLecture):
    """Tous les essais ont échoué : l'enregistrement passe à l'état ECHEC_TRAITEMENT (shared/statuts.json)."""
    etat = "ECHEC_TRAITEMENT"


def cle_cache(sha_image, type_page, version_prompt, modele):
    return hashlib.sha256(f"{sha_image}|{type_page}|{version_prompt}|{modele}".encode()).hexdigest()


def cout_usd(modele, jetons_entree, jetons_sortie):
    entree, sortie = PRIX.get(modele, (0.0, 0.0))
    return (jetons_entree * entree + jetons_sortie * sortie) / 1_000_000


# ---------- Fournisseurs ----------

def appeler_anthropic(image, media_type, prompt, definition_outil, modele, effort=None):
    """Un appel (avec nouvel essai si le modèle répond sans outil).

    effort : None = réglage par défaut du modèle ; sinon "medium" ou "low" (output_config.effort).
    Renvoie {"entree": dict ou None, "tronque": bool, "jetons_entree", "jetons_sortie", "jetons_reflexion"}.
    """
    import anthropic
    client = anthropic.Anthropic(max_retries=4)  # coupures réseau : 4 nouvelles tentatives au lieu de 2
    consigne = (f"Réponds uniquement en appelant l'outil {definition_outil['name']}, "
                "une seule fois, avec tous les champs.")
    contenu_texte = consigne
    options = {"output_config": {"effort": effort}} if effort else {}
    resultat = {"entree": None, "tronque": False, "jetons_entree": 0, "jetons_sortie": 0, "jetons_reflexion": 0}
    for essai in range(1, ESSAIS_MAX + 1):
        # Streaming : GROSSESSE_ACTUELLE produit ~12 000 jetons de sortie ; une limite haute
        # sans streaming risquerait un dépassement de délai HTTP.
        with client.messages.stream(
            model=modele,
            max_tokens=MAX_JETONS_SORTIE,
            system=prompt,
            tools=[definition_outil],
            tool_choice={"type": "auto"},
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image}},
                {"type": "text", "text": contenu_texte},
            ]}],
            **options,
        ) as flux:
            reponse = flux.get_final_message()
        usage = reponse.usage
        resultat["jetons_entree"] += usage.input_tokens
        resultat["jetons_sortie"] += usage.output_tokens
        if usage.output_tokens_details is not None:
            resultat["jetons_reflexion"] += usage.output_tokens_details.thinking_tokens
        if reponse.stop_reason == "refusal":
            raise ErreurLecture("le modèle a refusé la requête")
        if reponse.stop_reason == "max_tokens":
            resultat["tronque"] = True
            return resultat
        resultat["entree"] = next((b.input for b in reponse.content if b.type == "tool_use"
                                   and b.name == definition_outil["name"]), None)
        if resultat["entree"] is not None:
            break
        print(f"  essai {essai} : réponse sans appel d'outil, nouvel essai")
        contenu_texte = (consigne + " Ta réponse précédente ne contenait pas d'appel à l'outil : "
                         "n'écris aucun texte, appelle directement l'outil.")
    return resultat


def appeler_simule(image, media_type, prompt, definition_outil, modele, effort=None):
    """Aucun appel réseau : tous les champs NON_FOURNI (pour tester sans clé ni coût)."""
    vide = {"valeur": "", "statut": "NON_FOURNI", "confiance": 0.0, "texte_lu": ""}
    proprietes = definition_outil["input_schema"]["properties"]
    if definition_outil["name"] == "type_de_page":
        entree = {"type_page": proprietes["type_page"]["enum"][0], "confiance": 0.0}
    else:
        entree = {cle: ([] if cle == "visites" else dict(vide)) for cle in proprietes if cle != "cases_a_cocher"}
    return {"entree": entree, "tronque": False, "jetons_entree": 0, "jetons_sortie": 0, "jetons_reflexion": 0}


FOURNISSEURS = {"anthropic": appeler_anthropic, "simule": appeler_simule}


# ---------- Point d'entrée ----------

def lire_page(image_path, type_page, prompt, version_prompt, modele=None, definition_outil=None):
    """Lit une page avec le modèle (ou depuis le cache).

    definition_outil : outil à utiliser (par défaut outil(type_page)) ; son empreinte entre
    dans la version, pour qu'un changement de format n'utilise jamais une ancienne lecture.
    Renvoie {"entree": dict, "modele", "fournisseur", "jetons_entree", "jetons_sortie",
             "cout_usd", "duree_s", "depuis_cache"}.
    """
    chemin = Path(image_path)
    if not chemin.is_absolute():
        chemin = RACINE / chemin
    return lire_octets(chemin.read_bytes(), TYPES_MEDIA[chemin.suffix.lower()], chemin.name, type_page,
                       prompt, version_prompt, modele or MODELE_DEFAUT, definition_outil or outil(type_page))


def detecter_type_page(image_path):
    """Appel léger : envoie seulement le haut de la page, réduit, pour lire le titre.

    Renvoie {"type_page": str, "confiance": float, ...infos d'appel}. Modèle : EXTRACTION_MODELE_DETECTION
    (claude-haiku-4-5 par défaut, le moins cher).
    """
    import io
    from PIL import Image
    from extraction.prompts import DETECTION
    from extraction.schema_outil import STATUTS

    chemin = Path(image_path)
    if not chemin.is_absolute():
        chemin = RACINE / chemin
    image = Image.open(chemin).convert("RGB")
    haut = image.crop((0, 0, image.width, int(image.height * 0.12)))  # titre + sous-titre
    haut.thumbnail((1000, 1000))
    tampon = io.BytesIO()
    haut.save(tampon, format="PNG")
    definition = {
        "name": "type_de_page", "strict": True,
        "description": "Type de la page d'après son titre.",
        "input_schema": {"type": "object", "additionalProperties": False,
                         "required": ["type_page", "confiance"],
                         "properties": {"type_page": {"type": "string", "enum": STATUTS["types_page"]},
                                        "confiance": {"type": "number"}}},
    }
    lecture = lire_octets(tampon.getvalue(), "image/png", chemin.name, "DETECTION", DETECTION["texte"],
                          DETECTION["version"], MODELE_DETECTION, definition)
    return {**lecture, "type_page": lecture["entree"]["type_page"], "confiance": lecture["entree"]["confiance"]}


# Niveaux d'effort essayés dans l'ordre : réglage par défaut (résultats déjà validés), puis, si la
# sortie est tronquée (réflexion trop longue sur une image difficile), medium puis low.
EFFORTS = [None, "medium", "low"]
CACHE_SEULEMENT = False  # True : aucun appel API, seules les lectures en cache sont utilisées


def lire_octets(octets, media_type, nom, type_page, prompt, version_prompt, modele, definition_outil):
    """Appel au modèle avec cache disque.

    Clé : sha256 des octets envoyés + type de page + version du prompt (+ empreinte de l'outil)
    + fournisseur/modèle + niveau d'effort (absent pour le réglage par défaut : anciennes clés valides).
    Chaque essai est mis en cache, y compris les sorties tronquées (avec leur coût) : un essai raté
    n'est jamais repayé et le coût total du cache est exact.
    Lève EchecTraitement (état ECHEC_TRAITEMENT) si tous les niveaux d'effort sont tronqués.
    """
    empreinte_outil = hashlib.sha256(json.dumps(definition_outil, sort_keys=True).encode()).hexdigest()[:12]
    sha_image = hashlib.sha256(octets).hexdigest()
    cout_echecs = 0.0
    for effort in EFFORTS:
        suffixe = f"/effort-{effort}" if effort else ""
        fichier_cache = CACHE / (cle_cache(sha_image, type_page, f"{version_prompt}+{empreinte_outil}",
                                           f"{FOURNISSEUR}/{modele}{suffixe}") + ".json")
        if fichier_cache.exists():
            resultat = json.loads(fichier_cache.read_text(encoding="utf-8"))
            if resultat.get("echec") == "tronque":
                cout_echecs += resultat["cout_usd"]
                continue
            resultat.update(depuis_cache=True, cout_essais_tronques=round(cout_echecs, 6))
            print(f"[cache] {nom} {type_page}{' effort ' + effort if effort else ''} : 0 $ (appel d'origine : "
                  f"{resultat['cout_usd']:.4f} $, {resultat['duree_s']:.1f} s)")
            return resultat

        if CACHE_SEULEMENT:
            raise ErreurLecture(f"{nom} {type_page} : absent du cache (mode cache seulement)")
        debut = time.perf_counter()
        r = FOURNISSEURS[FOURNISSEUR](base64.standard_b64encode(octets).decode("utf-8"), media_type,
                                      prompt, definition_outil, modele, effort)
        duree = time.perf_counter() - debut
        cout = cout_usd(modele, r["jetons_entree"], r["jetons_sortie"])
        print(f"[{FOURNISSEUR}/{modele}{' effort ' + effort if effort else ''}] {nom} {type_page} : {duree:.1f} s, "
              f"{r['jetons_entree']} + {r['jetons_sortie']} jetons (réflexion {r['jetons_reflexion']}), {cout:.4f} $"
              f"{' — TRONQUÉ' if r['tronque'] else ''}")
        resultat = {
            "entree": r["entree"], "modele": modele, "fournisseur": FOURNISSEUR, "effort": effort,
            "image_sha256": sha_image, "type_page": type_page, "version_prompt": version_prompt,
            "jetons_entree": r["jetons_entree"], "jetons_sortie": r["jetons_sortie"],
            "jetons_reflexion": r["jetons_reflexion"],
            "cout_usd": round(cout, 6), "duree_s": round(duree, 2),
            "date": datetime.now().isoformat(timespec="seconds"),
        }
        if r["tronque"]:
            resultat["echec"] = "tronque"
        elif r["entree"] is None:
            raise ErreurLecture(f"aucun appel d'outil après {ESSAIS_MAX} essais")
        CACHE.mkdir(exist_ok=True)
        fichier_cache.write_text(json.dumps(resultat, ensure_ascii=False, indent=1), encoding="utf-8")
        if r["tronque"]:
            cout_echecs += cout
            continue
        resultat.update(depuis_cache=False, cout_essais_tronques=round(cout_echecs, 6))
        return resultat
    raise EchecTraitement(f"{nom} {type_page} : sortie tronquée à tous les niveaux d'effort "
                          f"({cout_echecs:.4f} $ dépensés)")


if __name__ == "__main__":
    # Prompt minimal pour tester le client ; les vrais prompts arrivent avec prompts.py (étape 5).
    PROMPT_ESSAI = ("Tu transcris une page d'un registre maternel papier (données synthétiques). "
                    "Ne recopie jamais de nom, prénom, CIN, téléphone ni adresse.")
    image = "data/Paper Registry/dossiers_specimen_10_patientes-01.png"  # patiente 1 (dev)
    for _ in range(2):
        r = lire_page(image, "IDENTIFICATION", PROMPT_ESSAI, "essai-client-0")
    print("\nDepuis le cache :", r["depuis_cache"])
    print(json.dumps(r["entree"], ensure_ascii=False, indent=1))
