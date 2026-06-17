"""Pipeline / Kanban board ("el foso").

Each card is one selection process (an Application), regardless of the source
portal. Supports moving between stages, archiving without deleting, per-stage
custom fields (stored as JSON), notes timeline and follow-up reminders.
"""

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import joinedload

from src.db.database import get_session
from src.db.models import Application, ApplicationNote, Reminder

router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent.parent / "web" / "templates")
)

# Stage definitions (key, label, dot color).
STAGES = [
    ("guardado", "Guardado", "#888780"),
    ("postulado", "Postulado", "#185FA5"),
    ("contactado", "Contactado", "#534AB7"),
    ("entrevista", "Entrevista", "#BA7517"),
    ("oferta", "Oferta", "#0F6E56"),
    ("cerrado", "Cerrado", "#639922"),
]

# Keep the legacy Application.status in sync so the dashboard counters still work.
_STAGE_TO_STATUS = {
    "guardado": "pending",
    "postulado": "applied",
    "contactado": "applied",
    "entrevista": "interview",
    "oferta": "offer",
    "cerrado": "rejected",
}


def _load_details(app: Application) -> dict:
    try:
        return json.loads(app.details) if app.details else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _card(app: Application) -> dict:
    return {
        "id": app.id,
        "stage": app.stage,
        "priority": app.priority,
        "archived": app.archived,
        "stage_entered_at": str(app.stage_entered_at)[:10] if app.stage_entered_at else "",
        "title": app.job.title if app.job else "",
        "company": app.job.company if app.job else "",
        "platform": app.job.platform if app.job else "",
        "url": app.job.url if app.job else "",
        "details": _load_details(app),
    }


# ── Page ──────────────────────────────────────────────────────

@router.get("/pipeline", response_class=HTMLResponse)
def pipeline_page(request: Request):
    session = get_session()
    apps = (
        session.query(Application)
        .options(joinedload(Application.job))
        .filter(Application.archived.is_(False))
        .order_by(Application.updated_at.desc())
        .all()
    )
    columns = {key: [] for key, _, _ in STAGES}
    for app in apps:
        stage = app.stage if app.stage in columns else "postulado"
        columns[stage].append(_card(app))
    session.close()
    return templates.TemplateResponse(
        request, "pipeline.html", {"stages": STAGES, "columns": columns}
    )


# ── Card detail ───────────────────────────────────────────────

@router.get("/api/pipeline/{app_id}")
def get_card(app_id: int):
    session = get_session()
    app = (
        session.query(Application)
        .options(
            joinedload(Application.job),
            joinedload(Application.pipeline_notes),
            joinedload(Application.reminders),
        )
        .get(app_id)
    )
    if not app:
        session.close()
        raise HTTPException(status_code=404, detail="Proceso no encontrado")
    data = _card(app)
    data["notes"] = [
        {"id": n.id, "content": n.content, "created_at": str(n.created_at)[:16]}
        for n in sorted(app.pipeline_notes, key=lambda n: n.created_at, reverse=True)
    ]
    data["reminders"] = [
        {
            "id": r.id,
            "due_date": str(r.due_date)[:10] if r.due_date else "",
            "note": r.note or "",
            "done": r.done,
        }
        for r in sorted(app.reminders, key=lambda r: (r.due_date or datetime.max))
    ]
    session.close()
    return data


@router.post("/api/pipeline/{app_id}/stage")
def move_stage(app_id: int, stage: str = Body(..., embed=True)):
    valid = {key for key, _, _ in STAGES}
    if stage not in valid:
        raise HTTPException(status_code=400, detail="Etapa inválida")
    session = get_session()
    try:
        app = session.query(Application).get(app_id)
        if not app:
            raise HTTPException(status_code=404, detail="Proceso no encontrado")
        app.stage = stage
        app.stage_entered_at = datetime.utcnow()
        app.status = _STAGE_TO_STATUS.get(stage, app.status)
        if stage in ("postulado", "contactado", "entrevista", "oferta") and not app.applied_at:
            app.applied_at = datetime.utcnow()
        session.commit()
        return {"ok": True, "stage": stage}
    finally:
        session.close()


@router.patch("/api/pipeline/{app_id}")
def update_card(app_id: int, payload: dict = Body(...)):
    session = get_session()
    try:
        app = session.query(Application).get(app_id)
        if not app:
            raise HTTPException(status_code=404, detail="Proceso no encontrado")
        if "details" in payload and isinstance(payload["details"], dict):
            current = _load_details(app)
            current.update({k: v for k, v in payload["details"].items()})
            app.details = json.dumps(current, ensure_ascii=False)
        if "priority" in payload:
            app.priority = payload["priority"] or None
        if "outcome" in payload:
            app.outcome = payload["outcome"] or None
        session.commit()
        return {"ok": True}
    finally:
        session.close()


@router.post("/api/pipeline/{app_id}/notes")
def add_note(app_id: int, content: str = Body(..., embed=True)):
    if not content.strip():
        raise HTTPException(status_code=400, detail="La nota está vacía")
    session = get_session()
    try:
        app = session.query(Application).get(app_id)
        if not app:
            raise HTTPException(status_code=404, detail="Proceso no encontrado")
        note = ApplicationNote(application_id=app_id, content=content.strip())
        session.add(note)
        session.commit()
        return {"ok": True, "id": note.id, "created_at": str(note.created_at)[:16]}
    finally:
        session.close()


@router.post("/api/pipeline/{app_id}/reminder")
def add_reminder(app_id: int, payload: dict = Body(...)):
    session = get_session()
    try:
        app = session.query(Application).get(app_id)
        if not app:
            raise HTTPException(status_code=404, detail="Proceso no encontrado")
        due = None
        raw = (payload.get("due_date") or "").strip()
        if raw:
            try:
                due = datetime.fromisoformat(raw)
            except ValueError:
                due = None
        rem = Reminder(application_id=app_id, due_date=due, note=(payload.get("note") or "").strip())
        session.add(rem)
        session.commit()
        return {"ok": True, "id": rem.id}
    finally:
        session.close()


@router.post("/api/pipeline/{app_id}/archive")
def archive_card(app_id: int):
    session = get_session()
    try:
        app = session.query(Application).get(app_id)
        if not app:
            raise HTTPException(status_code=404, detail="Proceso no encontrado")
        app.archived = not app.archived
        session.commit()
        return {"ok": True, "archived": app.archived}
    finally:
        session.close()


@router.post("/api/pipeline/add-job/{job_id}")
def add_job_to_pipeline(job_id: int):
    """Add a scraped job to the pipeline at the 'guardado' stage."""
    from src.db.models import Job, Resume

    session = get_session()
    try:
        job = session.query(Job).get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Empleo no encontrado")
        resume = session.query(Resume).filter_by(is_active=True).first()
        if not resume:
            raise HTTPException(
                status_code=400,
                detail="Sube tu hoja de vida primero para usar el pipeline.",
            )
        existing = session.query(Application).filter_by(job_id=job_id).first()
        if existing:
            existing.archived = False
            session.commit()
            return {"ok": True, "application_id": existing.id, "existing": True}
        app = Application(
            job_id=job_id,
            resume_id=resume.id,
            status="pending",
            stage="guardado",
            stage_entered_at=datetime.utcnow(),
        )
        session.add(app)
        session.commit()
        return {"ok": True, "application_id": app.id}
    finally:
        session.close()
