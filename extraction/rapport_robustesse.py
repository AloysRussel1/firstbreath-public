"""Rapport de robustesse sur les images dégradées, en lisant uniquement le cache (aucun appel API).

Référence : l'extraction de la page propre d'origine (98,9 % de valeurs exactes sur le dev d'après
evaluation/). Les champs que la page propre met elle-même en A_REVISER sont exclus de la comparaison.

Catégories, pour chaque champ d'une image dégradée :
- accord                      : même valeur et même statut que la page propre ;
- doute justifié              : A_REVISER et la lecture diffère de la page propre ;
- fausse alerte               : A_REVISER alors que la valeur est identique à la page propre ;
- valeur fausse sans alerte   : CONNU des deux côtés, valeurs différentes (le cas dangereux) ;
- statut changé sans alerte   : autre statut que la page propre, sans A_REVISER.

Usage (depuis la racine, venv activé) :
    python extraction/rapport_robustesse.py     # écrit extraction/rapports/robustesse_degradations.md
"""
import contextlib
import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from extraction import client
from extraction.pipeline import CLES_CONTRAT, extraire
from shared.valider import valider_page

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "extraction/rapports/robustesse_degradations.md"
CATEGORIES = ["accord", "doute justifié", "fausse alerte", "valeur fausse sans alerte", "statut changé sans alerte"]


def classer(c, p):
    """Catégorie d'un champ dégradé c par rapport au champ propre p (None si p est déjà douteux)."""
    if p["statut"] == "A_REVISER":
        return None
    if (c["valeur"], c["statut"]) == (p["valeur"], p["statut"]):
        return "accord"
    if c["statut"] == "A_REVISER":
        return "fausse alerte" if c["valeur"] == p["valeur"] and p["statut"] == "CONNU" else "doute justifié"
    if c["statut"] == p["statut"] == "CONNU":
        return "valeur fausse sans alerte"
    return "statut changé sans alerte"


def generique(cle):
    return re.sub(r"\[\d\]", "[*]", cle)


def lectures_cache():
    """Toutes les entrées du cache, groupées par sha256 de l'image envoyée."""
    par_sha = defaultdict(list)
    for f in (RACINE / "extraction/cache").glob("*.json"):
        r = json.loads(f.read_text(encoding="utf-8"))
        par_sha[r["image_sha256"]].append(r)
    return par_sha


def reflexion(lectures, ratio):
    """Jetons de réflexion de la lecture retenue : mesurés si disponibles, sinon estimés
    (sortie totale - taille du JSON de l'outil / ratio caractères par jeton)."""
    r = next((x for x in lectures if not x.get("echec") and x["type_page"] != "DETECTION"), None)
    if r is None:
        return None, None
    if r.get("jetons_reflexion") is not None:
        return r["jetons_reflexion"], "mesuré"
    taille = len(json.dumps(r["entree"], ensure_ascii=False))
    return max(0, round(r["jetons_sortie"] - taille / ratio)), "estimé"


def spearman(x, y):
    def rangs(v):
        ordre = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[ordre[j + 1]] == v[ordre[i]]:
                j += 1
            for k in range(i, j + 1):
                r[ordre[k]] = (i + j) / 2
            i = j + 1
        return r
    rx, ry = rangs(x), rangs(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    var = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return cov / var if var else 0.0


def main():
    client.CACHE_SEULEMENT = True
    index = json.loads((RACINE / "extraction/degradees/index_degradees.json").read_text(encoding="utf-8"))["images"]
    retenues = [i for i in index if i["degradation"] == "combinaison" or i["patiente"] in (1, 2)]
    cache = lectures_cache()

    # Ratio caractères/jeton du JSON de l'outil, calibré sur les lectures où la réflexion est mesurée.
    calib = [(len(json.dumps(r["entree"], ensure_ascii=False)), r["jetons_sortie"] - r["jetons_reflexion"])
             for rs in cache.values() for r in rs
             if r.get("jetons_reflexion") is not None and not r.get("echec") and r["type_page"] != "DETECTION"]
    ratio = sum(c for c, _ in calib) / sum(t for _, t in calib) if calib else 2.5

    var = defaultdict(lambda: {"attendues": 0, "valides": 0, "echecs": 0, "statuts": Counter(), "cat": Counter(),
                               "cat_avant": Counter(), "nouvelles_alertes": [],
                               "cout": 0.0, "duree": 0.0, "appels": 0, "tronques": 0, "efforts": Counter()})
    silencieuses = defaultdict(list)
    pages = []  # (variante, type, réflexion dégradée, réflexion propre, nb doutes, nb silencieuses, champs comparés)
    for i in retenues:
        v = var[i["degradation"]]
        v["attendues"] += 1
        lectures = [r for r in cache.get(i["sha256"], []) if r["type_page"] != "DETECTION"]
        v["cout"] += sum(r["cout_usd"] for r in lectures)
        v["duree"] += sum(r["duree_s"] for r in lectures)
        v["appels"] += len(lectures)
        v["tronques"] += sum(bool(r.get("echec")) for r in lectures)
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                avant = extraire(RACINE / i["fichier"], confiance_finale=False)   # sans confiance.py
                deg = extraire(RACINE / i["fichier"])                             # avec confiance finale
                propre = extraire(RACINE / i["fichier_origine"], confiance_finale=False)
            except Exception:
                v["echecs"] += 1
                continue
        v["efforts"][deg.get("effort") or "défaut"] += 1
        contrat = {"type_page": deg["type_page"], "champs": [{k: c[k] for k in CLES_CONTRAT} for c in deg["champs"]]}
        v["valides"] += not valider_page(contrat)[0]
        v["statuts"].update(c["statut"] for c in deg["champs"])
        ref = {c["champ"]: c for c in propre["champs"]}
        par_cle_avant = {c["champ"]: c for c in avant["champs"]}
        doutes = silence = compares = 0
        for c in deg["champs"]:
            p, a = ref[c["champ"]], par_cle_avant[c["champ"]]
            cat, cat_avant = classer(c, p), classer(a, p)
            if cat is None:
                continue  # référence elle-même douteuse
            compares += 1
            v["cat"][cat] += 1
            v["cat_avant"][cat_avant] += 1
            if cat_avant in ("doute justifié", "fausse alerte"):
                doutes += 1
            elif cat_avant in ("valeur fausse sans alerte", "statut changé sans alerte"):
                silence += 1
            if cat_avant == "valeur fausse sans alerte":
                silencieuses[generique(c["champ"])].append(
                    (i["degradation"], i["page_pdf"], p["valeur"], a["valeur"], a["confiance"],
                     c["statut"] == "A_REVISER", c["signaux"]["raison"]))
            if cat_avant == "accord" and cat == "fausse alerte":
                v["nouvelles_alertes"].append((i["page_pdf"], c["champ"], c["signaux"]["raison"]))
        r_deg, mode = reflexion(cache.get(i["sha256"], []), ratio)
        r_prop, _ = reflexion(cache.get(i["sha256_origine"], []), ratio)
        pages.append((i["degradation"], deg["type_page"], r_deg, r_prop, doutes, silence, compares, mode))

    # ---------- Rapport ----------
    L = ["# Robustesse de l'extraction sur images dégradées", "",
         "Généré par `extraction/rapport_robustesse.py` en lisant uniquement le cache (aucun appel API).",
         "Modèle : `claude-sonnet-5` ; nouvel essai à effort medium puis low si la sortie est tronquée.", "",
         "Images : dégradation `combinaison` sur les 48 pages de dev (patientes 1 à 6), "
         "5 autres dégradations sur les patientes 1 et 2 (16 pages chacune) : "
         f"{len(retenues)} images. Reproductibles avec `extraction/degrader.py` (pillow==12.3.0).", "",
         "Référence : extraction de la page propre d'origine (98,9 % de valeurs exactes sur le dev "
         "d'après `evaluation/`) ; les champs déjà A_REVISER sur la page propre sont exclus.", "",
         "Les images dégradées sont classées **avec la confiance finale** (`extraction/confiance.py` : "
         "cohérence entre champs et signal de réflexion) ; la section « Effet de la confiance finale » "
         "compare avec le classement sans cette couche.", "",
         "## Vue d'ensemble", "",
         "| Dégradation | Pages | Valides | Échecs | Accord | Doute justifié | Fausse alerte | **Valeur fausse sans alerte** | Statut changé sans alerte | Coût $ | Temps s |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    total_cat, total = Counter(), Counter()
    for nom in ["flou", "rotation", "ombre", "sombre", "jpeg", "combinaison"]:
        v = var[nom]
        n = sum(v["cat"].values()) or 1
        total_cat.update(v["cat"])
        total.update(attendues=v["attendues"], valides=v["valides"], echecs=v["echecs"])
        total["cout"] += v["cout"]
        total["duree"] += v["duree"]
        cells = [f"{v['cat'][c] / n:.1%}" for c in CATEGORIES]
        cells[3] = f"**{cells[3]}**"
        L.append(f"| {nom} | {v['attendues']} | {v['valides']} | {v['echecs']} | " + " | ".join(cells)
                 + f" | {v['cout']:.2f} | {v['duree']:.0f} |")
    n = sum(total_cat.values()) or 1
    cells = [f"{total_cat[c] / n:.1%}" for c in CATEGORIES]
    L.append(f"| **total** | {total['attendues']} | {total['valides']} | {total['echecs']} | " + " | ".join(cells)
             + f" | {total['cout']:.2f} | {total['duree']:.0f} |")
    L += ["", f"Champs comparés : {n}. Coût et temps incluent les essais tronqués "
          f"({sum(v['tronques'] for v in var.values())} essais tronqués ; effort de la lecture retenue : "
          f"{dict(sum((v['efforts'] for v in var.values()), Counter()))}).", "",
          "Statuts des champs par dégradation :", ""]
    for nom in ["flou", "rotation", "ombre", "sombre", "jpeg", "combinaison"]:
        L.append(f"- {nom} : {dict(sorted(var[nom]['statuts'].items()))}")

    doutes = total_cat["doute justifié"] + total_cat["fausse alerte"]
    L += ["", "## Doutes justifiés contre fausses alertes", "",
          f"Sur {doutes} champs mis en A_REVISER par les dégradations : {total_cat['doute justifié']} doutes justifiés "
          f"({total_cat['doute justifié'] / max(doutes, 1):.1%}) et {total_cat['fausse alerte']} fausses alertes "
          f"({total_cat['fausse alerte'] / max(doutes, 1):.1%}, valeur correcte mais doute exprimé).", "",
          "Une fausse alerte coûte une question de plus à la sage-femme ; un doute justifié évite une erreur.", ""]

    # Effet de la confiance finale
    avant = sum((v["cat_avant"] for v in var.values()), Counter())
    toutes_silencieuses = [x for cas in silencieuses.values() for x in cas]
    attrapees = [x for x in toutes_silencieuses if x[5]]
    nouvelles = [a for v in var.values() for a in v["nouvelles_alertes"]]
    L += ["## Effet de la confiance finale", "",
          "| Catégorie | Sans confiance finale | Avec confiance finale |", "|---|---:|---:|"]
    for c in CATEGORIES:
        L.append(f"| {c} | {avant[c]} | {total_cat[c]} |")
    L += ["", f"- **Valeurs fausses sans alerte attrapées : {len(attrapees)} sur {len(toutes_silencieuses)}** "
          f"(passées en A_REVISER par la cohérence ou le signal de réflexion).",
          f"- **Fausses alertes en plus : {len(nouvelles)}** (champs identiques à la page propre, désormais A_REVISER).",
          "- Pages propres : aucune nouvelle alerte (les règles de cohérence ne se déclenchent sur aucune des 48 pages "
          "propres, et leur ratio de réflexion reste sous le seuil)."]
    raisons_nouvelles = Counter(("cohérence" if r and ("SA" in r or "DDR" in r or "chronologique" in r or "rendez-vous" in r
                                                       or "parité" in r or "accouchement" in r) else "réflexion")
                                for _, _, r in nouvelles)
    if nouvelles:
        L.append(f"- Origine des fausses alertes en plus : {dict(raisons_nouvelles)}.")
    L += ["", "## Valeurs fausses sans alerte (avant confiance finale), par champ", "",
          f"{len(toutes_silencieuses)} champs CONNU avec une valeur différente de la page propre, sans A_REVISER "
          f"avant la confiance finale (+ {avant['statut changé sans alerte']} changements de statut sans A_REVISER). "
          "✓ = attrapée par la confiance finale.", "",
          "| Champ | Nombre | Attrapées | Exemples (dégradation, page : propre -> dégradée, confiance, attrapée) |", "|---|---:|---:|---|"]
    for cle, cas in sorted(silencieuses.items(), key=lambda kv: -len(kv[1])):
        ex = " ; ".join(f"{d} p.{pg} : {json.dumps(a, ensure_ascii=False)} -> {json.dumps(b, ensure_ascii=False)} "
                        f"({cf:.2f}{', ✓' if pris else ''})" for d, pg, a, b, cf, pris, _ in cas[:3])
        L.append(f"| `{cle}` | {len(cas)} | {sum(x[5] for x in cas)} | {ex} |")

    # Réflexion et erreurs
    util = [p for p in pages if p[2] is not None and p[3]]
    L += ["", "## Réflexion du modèle et erreurs", "",
          "Jetons de réflexion : mesurés (`usage.output_tokens_details.thinking_tokens`) pour les lectures récentes, "
          f"sinon estimés (sortie totale - JSON de l'outil, {ratio:.2f} caractères par jeton calibrés sur "
          f"{len(calib)} lectures mesurées). Surcroît = réflexion dégradée / réflexion de la page propre.", ""]
    if util:
        surcroit = [p[2] / p[3] for p in util]
        taux_doute = [p[4] / max(p[6], 1) for p in util]
        taux_silence = [p[5] / max(p[6], 1) for p in util]
        L += [f"Corrélation de Spearman sur {len(util)} pages : surcroît de réflexion / taux de doutes "
              f"= {spearman(surcroit, taux_doute):+.2f} ; surcroît / taux d'erreurs sans alerte "
              f"= {spearman(surcroit, taux_silence):+.2f}.", "",
              "| Surcroît de réflexion | Pages | Doutes par champ | Erreurs sans alerte par champ |", "|---|---:|---:|---:|"]
        tri = sorted(zip(surcroit, util), key=lambda t: t[0])
        tiers = [tri[: len(tri) // 3], tri[len(tri) // 3: 2 * len(tri) // 3], tri[2 * len(tri) // 3:]]
        for nom, groupe in zip(["faible", "moyen", "fort"], tiers):
            if groupe:
                d = sum(p[4] for _, p in groupe) / max(sum(p[6] for _, p in groupe), 1)
                s = sum(p[5] for _, p in groupe) / max(sum(p[6] for _, p in groupe), 1)
                L.append(f"| {nom} (x{groupe[0][0]:.1f} à x{groupe[-1][0]:.1f}) | {len(groupe)} | {d:.1%} | {s:.2%} |")
        par_type = defaultdict(list)
        for p in util:
            par_type[p[1]].append(p[2] / p[3])
        L += ["", "Surcroît médian de réflexion par type de page : "
              + ", ".join(f"{t} x{sorted(v)[len(v) // 2]:.1f}" for t, v in sorted(par_type.items())) + "."]
    L += ["", "## Limites", "",
          "- La référence est l'extraction propre, pas la vérité terrain : ses rares erreurs (1,1 %) comptent ici comme accords.",
          "- Les 5 dégradations simples ne portent que sur les patientes 1 et 2 (16 pages chacune).",
          "- Jetons de réflexion estimés pour les lectures antérieures au suivi : ordre de grandeur, pas mesure exacte.", ""]
    SORTIE.parent.mkdir(exist_ok=True)
    SORTIE.write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
