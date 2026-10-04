"""HTTP API for FirstBreath's local-first maternity register workflow."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend import database, services
from backend.constants import ALLOWED_PAGE_TYPES, CHAMPS, CONFIDENCE_THRESHOLD, MAX_UPLOAD_BYTES, REQUIRED_FIELDS, SCHEMA, STATUTS


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.initialize()
    services.reprendre_interrompus()
    yield


app = FastAPI(title="FirstBreath API", version="1.0.0", lifespan=lifespan)
origins = [item.strip() for item in os.getenv("FIRSTBREATH_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "PATCH", "OPTIONS"], allow_headers=["*"])


@app.exception_handler(services.ServiceError)
async def service_error_handler(_: Request, exc: services.ServiceError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/sante")
def health():
    return {"ok": True, "service": "firstbreath-api"}


@app.get("/schema")
def schema():
    """Schéma pour l'interface : champs et libellés (shared/schema_champs.json), visites, statuts, seuil."""
    visites = next(page["visites"] for page in SCHEMA["pages"].values() if "visites" in page)
    return {
        "fields": CHAMPS,
        "required_fields": list(REQUIRED_FIELDS),
        "page_types": list(ALLOWED_PAGE_TYPES),
        # Champs de visite : clé complète grossesse.visites[i].<cle>, i dans l'ordre de visites.index.
        "visites": {"index": visites["index"], "champs": {c["cle"]: c for c in visites["champs"]}},
        "pages": {nom: [c["cle"] for c in page["champs"]] + (["grossesse.visites[*]"] if "visites" in page else [])
                  for nom, page in SCHEMA["pages"].items()},
        "statuts_champ": STATUTS["statuts_champ"],
        "seuil_question_suivi": CONFIDENCE_THRESHOLD,
        # « simule » : aucune lecture réelle (tous les champs reviennent vides) ; l'interface le signale.
        "fournisseur_extraction": _fournisseur(),
    }


def _fournisseur() -> str:
    try:
        from extraction import client
        return client.FOURNISSEUR
    except Exception:  # dépendances d'extraction absentes : pas de lecture possible
        return "indisponible"


@app.post("/captures")
async def upload_capture(
    image: UploadFile = File(...),
    session_id: str = Form(...),
    page_no: int = Form(...),
    sage_femme_id: str = Form(...),
    idempotency_key: str | None = Form(None),
):
    content = await image.read(MAX_UPLOAD_BYTES + 1)
    return services.create_capture(
        image_bytes=content,
        content_type=image.content_type,
        session_id=session_id,
        page_no=page_no,
        actor_id=sage_femme_id,
        idempotency_key=idempotency_key,
    )


@app.post("/captures/{capture_id}/traiter")
def process_capture(capture_id: str, x_sage_femme_id: str | None = Header(None)):
    """Répond tout de suite (EN_ATTENTE_IA) ; l'extraction tourne en tâche de fond. Suivre /etat."""
    return services.traiter_en_fond(capture_id, x_sage_femme_id)


@app.get("/captures/{capture_id}/etat")
def capture_state(capture_id: str):
    """État du traitement : etat, termine, progression (0 à 1), duree_estimee_s, ecoule_s, detail."""
    return services.etat_capture(capture_id)


@app.get("/captures/{capture_id}")
def capture_metadata(capture_id: str):
    """Métadonnées : état, sha256, date de capture, sage-femme, dossier, type de page (sans l'image)."""
    return services.capture_info(capture_id)


@app.get("/captures/{capture_id}/image")
def capture_image(capture_id: str, x_role: str | None = Header(None), x_sage_femme_id: str | None = Header(None)):
    """Image d'origine : SUPERVISEUR -> toutes ; SAGE_FEMME -> seulement ses propres captures."""
    chemin, media_type = services.lire_image(capture_id, x_role, x_sage_femme_id)
    return FileResponse(chemin, media_type=media_type, headers={"Cache-Control": "no-store"})


@app.get("/dossiers")
def list_dossiers(x_role: str | None = Header(None), x_sage_femme_id: str | None = Header(None)):
    """Liste et états : SUPERVISEUR -> tous les dossiers ; SAGE_FEMME -> les siens."""
    return {"dossiers": services.lister_dossiers(x_role, x_sage_femme_id)}


@app.get("/patientes")
def list_patientes(x_role: str | None = Header(None), x_sage_femme_id: str | None = Header(None)):
    """Patientes par code de liaison, avec l'historique des visites visibles pour ce rôle."""
    return {"patientes": services.lister_patientes(x_role, x_sage_femme_id)}


@app.get("/dossiers/{dossier_id}")
def get_dossier(dossier_id: str):
    dossier = services.get_record(dossier_id)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    return dossier


@app.patch("/dossiers/{dossier_id}/champs")
async def update_field(dossier_id: str, request: Request, x_sage_femme_id: str | None = Header(None)):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object.")
    actor_id = x_sage_femme_id or "sage-femme-local"
    dossier = services.patch_field(dossier_id, payload, actor_id)
    return {"dossier": dossier, "validation": services.validation_result(dossier)}


@app.post("/dossiers/{dossier_id}/confirmer")
async def confirm_fields(dossier_id: str, request: Request, x_sage_femme_id: str | None = Header(None)):
    """Confirme en un geste les champs fiables (CONNU, confiance >= seuil). Corps : {"champs": [...]} facultatif."""
    payload = await request.json() if await request.body() else {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object.")
    return services.confirmer_champs(dossier_id, payload.get("champs"), x_sage_femme_id or "sage-femme-local")


@app.get("/dossiers/{dossier_id}/validation")
def get_validation(dossier_id: str):
    dossier = services.get_record(dossier_id)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    return services.validation_result(dossier)


@app.post("/dossiers/{dossier_id}/validate")
def validate_dossier(dossier_id: str, x_sage_femme_id: str | None = Header(None)):
    return services.validate_record(dossier_id, x_sage_femme_id or "sage-femme-local")


@app.get("/dossiers/{dossier_id}/historique")
def get_history(dossier_id: str):
    if services.get_record(dossier_id) is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    return services.record_history(dossier_id)


@app.get("/patientes/correspondances")
def patient_matches(numero_fiche: str | None = None, code: str | None = None):
    """Candidats par code de liaison et/ou N° de fiche ; la sage-femme choisit toujours elle-même."""
    if not numero_fiche and not code:
        raise HTTPException(status_code=422, detail="Provide numero_fiche or code.")
    return {"candidates": services.match_patients(numero_fiche, code)}


@app.post("/dossiers/{dossier_id}/renumerisation")
async def rescan(dossier_id: str, request: Request, x_sage_femme_id: str | None = Header(None)):
    """Corps : {"ancienne_page": n, "nouvelle_page": m, "champs": [clés à remplacer]}."""
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object.")
    return services.renumeriser(dossier_id, payload, x_sage_femme_id or "sage-femme-local")


@app.post("/dossiers/{dossier_id}/lier")
async def link_patient(dossier_id: str, request: Request, x_sage_femme_id: str | None = Header(None)):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object.")
    return services.link_patient(dossier_id, payload, x_sage_femme_id or "sage-femme-local")


@app.post("/dossiers/{dossier_id}/pages/{page_no}/retirer")
def remove_page(dossier_id: str, page_no: int, x_sage_femme_id: str | None = Header(None)):
    """Retire une page du dossier (page d'une autre patiente) ; la capture et l'image restent tracées."""
    return services.retirer_page(dossier_id, page_no, x_sage_femme_id or "sage-femme-local")


@app.post("/captures/{capture_id}/nouveau-registre")
async def move_capture(capture_id: str, request: Request, x_sage_femme_id: str | None = Header(None)):
    """Place la capture lue dans un nouveau registre. Corps : {"session_id": "...", "page_no": 1}."""
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object.")
    return services.deplacer_capture(capture_id, payload.get("session_id"), payload.get("page_no", 1), x_sage_femme_id or "sage-femme-local")


@app.post("/dossiers/{dossier_id}/enregistrer")
def save_dossier(dossier_id: str, x_sage_femme_id: str | None = Header(None)):
    """VALIDE ou PATIENTE_LIEE -> ENREGISTRE (registre numérique du centre)."""
    return services.enregistrer(dossier_id, x_sage_femme_id or "sage-femme-local")


@app.post("/synchronisation")
async def synchronise(request: Request, x_role: str | None = Header(None), x_sage_femme_id: str | None = Header(None)):
    """ENREGISTRE / ECHEC_SYNCHRONISATION -> SYNCHRONISE (copie anonymisée vers le système central simulé).
    Corps facultatif : {"simuler_panne": true} -> ECHEC_SYNCHRONISATION."""
    payload = await request.json() if await request.body() else {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object.")
    return services.synchroniser(x_role, x_sage_femme_id, bool(payload.get("simuler_panne")))


@app.get("/tableau-de-bord")
def dashboard(source: str = "dossiers"):
    """Agrégats anonymisés : source=dossiers (dossiers validés) ou source=demo (CSV synthétique des
    organisateurs). Toute case de moins de 5 dossiers est masquée."""
    return services.tableau_de_bord(source)


@app.post("/sync")
async def sync(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object.")
    return services.sync_records(payload)


@app.get("/sync/status")
def get_sync_status():
    return services.sync_status()


@app.post("/doublons/{report_id}/decision")
async def duplicate_decision(report_id: str, request: Request):
    payload = await request.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("decision"), str):
        raise HTTPException(status_code=422, detail="decision is required.")
    return services.resolve_duplicate(report_id, payload["decision"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
