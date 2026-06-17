import json
import re
from datetime import datetime

from fastapi import APIRouter, Body, HTTPException

from src.api.schemas import JobResponse, JobSearchRequest
from src.db.database import get_session
from src.db.models import Application, Job
from src.db.repository import JobRepo, ResumeRepo, SearchHistoryRepo
from src.scraper.models import SearchCriteria

router = APIRouter()


@router.get("/", response_model=list[JobResponse])
def list_jobs(limit: int = 50, offset: int = 0, search: str = ""):
    session = get_session()
    repo = JobRepo(session)
    if search:
        jobs = repo.search(search)
    else:
        jobs = repo.list_all(limit=limit, offset=offset)
    session.close()
    return jobs


@router.get("/suggestions")
def job_suggestions():
    """Suggest job-search queries based on the parsed resume (AI-assisted).

    Declared before /{job_id} so the path isn't captured as a job id.
    """
    session = get_session()
    resume = ResumeRepo(session).get_parsed_data()
    session.close()
    if not resume:
        return {"location": "", "queries": [], "reason": "no_resume"}

    skills = ", ".join(s.get("name", "") for s in (resume.get("skills") or [])[:12])
    exps = "; ".join(
        f"{e.get('title', '')} en {e.get('company', '')}"
        for e in (resume.get("experiences") or [])[:5]
    )
    profile = (
        f"Resumen: {resume.get('summary', '')}\n"
        f"Habilidades: {skills}\n"
        f"Experiencia: {exps}\n"
        f"Idiomas: {', '.join(resume.get('languages') or [])}"
    )

    from src.ai.client import get_client

    system = (
        "Eres un asesor de búsqueda de empleo. A partir del perfil del candidato "
        "propones consultas de búsqueda realistas (cargos o palabras clave) para "
        "portales de empleo. Respondes SOLO con JSON válido, sin markdown."
    )
    user = (
        "Perfil del candidato:\n" + profile + "\n\n"
        "Devuelve un objeto JSON con exactamente estas claves:\n"
        '- "location": ciudad o país sugerido como string (si no se infiere, "").\n'
        '- "queries": lista de 6 strings; cada uno un término de búsqueda de empleo '
        "(un cargo o palabra clave) adecuado al perfil.\n"
        "Solo JSON."
    )
    location = ""
    queries: list[str] = []
    error = ""
    try:
        raw = get_client().generate(system=system, user=user, max_tokens=400)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = json.loads(re.search(r"\{[\s\S]*\}", raw).group(0))
        queries = [str(q) for q in (data.get("queries") or []) if str(q).strip()][:8]
        location = str(data.get("location") or "")
    except Exception as exc:  # noqa: BLE001 - fall back to non-AI suggestions
        error = str(exc)

    # Fallback: derive suggestions straight from the resume so the panel is never
    # empty when the AI call fails or returns nothing.
    if not queries:
        queries = _fallback_queries(resume)

    return {"location": location, "queries": queries, "error": error}


def _fallback_queries(resume: dict) -> list[str]:
    """Build search suggestions directly from resume titles and skills."""
    candidates: list[str] = []
    for exp in (resume.get("experiences") or [])[:4]:
        title = str(exp.get("title") or "").strip()
        if title:
            candidates.append(title)
    for skill in (resume.get("skills") or [])[:6]:
        name = str(skill.get("name") or "").strip()
        if name:
            candidates.append(name)

    seen: set[str] = set()
    out: list[str] = []
    for q in candidates:
        key = q.lower()
        if key not in seen:
            seen.add(key)
            out.append(q)
    return out[:8]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int):
    session = get_session()
    job = JobRepo(session).get_by_id(job_id)
    session.close()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/preview")
def job_preview(job_id: int):
    """Return the offer details for an in-page preview modal.

    LinkedIn (and others) block iframe embedding, so instead of showing the live
    page we return the scraped offer. The description is fetched on demand when
    missing and cached back to the job row.
    """
    session = get_session()
    job = JobRepo(session).get_by_id(job_id)
    if not job:
        session.close()
        raise HTTPException(status_code=404, detail="Job not found")

    description = job.description or ""
    # Re-fetch if missing or suspiciously short (e.g. only a meta snippet cached).
    if (not description or len(description) < 300) and job.url:
        scraper = _get_scraper(job.platform)
        if scraper:
            try:
                details = scraper.get_details(job.url)
                if details and details.description:
                    description = details.description
                    job.description = description
                    session.commit()
            except Exception:  # noqa: BLE001 - preview is best-effort
                pass

    from src.cv.matcher import ai_match_score, match_score

    resume = ResumeRepo(session).get_parsed_data()
    match = None
    if resume:
        if job.match_score is None:
            ai = ai_match_score(resume, job.title, description)
            if ai is not None:
                job.match_score = ai
                session.commit()
        match = (
            job.match_score
            if job.match_score is not None
            else match_score(resume, job.title, description)
        )

    result = {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location or "",
        "url": job.url,
        "platform": job.platform,
        "description": description,
        "match": match,
        "saved": bool(job.saved),
    }
    session.close()
    return result


@router.post("/bulk")
def bulk_action(payload: dict = Body(...)):
    """Bulk save or delete jobs by id. action: 'save' | 'delete'."""
    action = payload.get("action")
    ids = [int(i) for i in (payload.get("ids") or [])]
    if not ids:
        return {"ok": True, "count": 0}
    session = get_session()
    try:
        if action == "save":
            session.query(Job).filter(Job.id.in_(ids)).update(
                {Job.saved: True}, synchronize_session=False
            )
        elif action == "delete":
            from src.db.models import ApplicationNote, Letter, Reminder

            apps = session.query(Application).filter(Application.job_id.in_(ids)).all()
            for a in apps:
                session.query(ApplicationNote).filter_by(application_id=a.id).delete(
                    synchronize_session=False
                )
                session.query(Reminder).filter_by(application_id=a.id).delete(
                    synchronize_session=False
                )
                session.query(Letter).filter_by(application_id=a.id).update(
                    {Letter.application_id: None}, synchronize_session=False
                )
            session.query(Application).filter(Application.job_id.in_(ids)).delete(
                synchronize_session=False
            )
            session.query(Job).filter(Job.id.in_(ids)).delete(synchronize_session=False)
        else:
            raise HTTPException(status_code=400, detail="Acción inválida")
        session.commit()
        return {"ok": True, "count": len(ids)}
    finally:
        session.close()


@router.post("/compute-matches")
def compute_matches(payload: dict = Body(...)):
    """Compute the AI fit % for jobs in a view that don't have one yet (cached)."""
    view = payload.get("view", "found")
    session = get_session()
    q = session.query(Job).filter(Job.match_score.is_(None))
    if view == "saved":
        q = q.filter(Job.saved.is_(True))
    else:
        q = q.filter(Job.from_last_search.is_(True))
    jobs = q.limit(80).all()
    resume = ResumeRepo(session).get_parsed_data()
    items = [(j.id, j.title, j.description or "") for j in jobs]
    session.close()

    if not resume or not items:
        return {"ok": True, "count": 0}

    from concurrent.futures import ThreadPoolExecutor

    from src.cv.matcher import ai_match_score

    def work(it):
        jid, title, desc = it
        return jid, ai_match_score(resume, title, desc)

    results = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for jid, score in ex.map(work, items):
            if score is not None:
                results[jid] = score

    session2 = get_session()
    try:
        for jid, score in results.items():
            session2.query(Job).filter_by(id=jid).update({Job.match_score: score})
        session2.commit()
    finally:
        session2.close()
    return {"ok": True, "count": len(results)}


@router.post("/manual")
def add_manual(payload: dict = Body(...)):
    """Add a vacancy the user found/applied to manually (by URL). If they already
    applied, it enters the Kanban (Seguimiento) at the 'postulado' stage."""
    import hashlib

    from src.db.models import Resume

    title = (payload.get("title") or "").strip() or "Vacante manual"
    url = (payload.get("url") or "").strip()
    applied = bool(payload.get("applied"))
    session = get_session()
    try:
        ext = "manual-" + hashlib.md5((url or title).encode()).hexdigest()[:12]
        job = Job(
            external_id=ext,
            platform="manual",
            title=title,
            company=(payload.get("company") or "").strip(),
            location=(payload.get("location") or "").strip(),
            url=url,
            saved=True,
            from_last_search=False,
        )
        session.add(job)
        session.commit()

        in_pipeline = False
        resume = session.query(Resume).filter_by(is_active=True).first()
        if resume:
            stage = "postulado" if applied else "guardado"
            app = Application(
                job_id=job.id,
                resume_id=resume.id,
                status="applied" if applied else "pending",
                stage=stage,
                stage_entered_at=datetime.utcnow(),
                applied_at=datetime.utcnow() if applied else None,
            )
            session.add(app)
            session.commit()
            in_pipeline = True
        return {"ok": True, "job_id": job.id, "applied": applied, "in_pipeline": in_pipeline}
    finally:
        session.close()


@router.post("/{job_id}/save")
def toggle_saved(job_id: int):
    """Bookmark / un-bookmark a job (shows up in the 'Guardados' tab)."""
    session = get_session()
    try:
        job = session.query(Job).get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Empleo no encontrado")
        job.saved = not job.saved
        session.commit()
        return {"ok": True, "saved": job.saved}
    finally:
        session.close()


@router.post("/{job_id}/applied")
def mark_applied(job_id: int):
    """Mark a job as applied so it shows up in the dashboard summary.

    Creates (or updates) an Application with status 'applied' for the active
    resume. Requires a resume to be loaded.
    """
    session = get_session()
    try:
        job = JobRepo(session).get_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Empleo no encontrado")

        resume = ResumeRepo(session).get_active()
        if not resume:
            raise HTTPException(
                status_code=400,
                detail="Sube tu hoja de vida primero para llevar el control de postulaciones.",
            )

        existing = session.query(Application).filter_by(job_id=job_id).first()
        if existing:
            existing.status = "applied"
            existing.applied_at = datetime.utcnow()
            existing.updated_at = datetime.utcnow()
            session.commit()
            app_id = existing.id
        else:
            app = Application(
                job_id=job_id,
                resume_id=resume.id,
                status="applied",
                applied_at=datetime.utcnow(),
            )
            session.add(app)
            session.commit()
            app_id = app.id

        return {"ok": True, "application_id": app_id, "status": "applied"}
    finally:
        session.close()


@router.post("/{job_id}/open-browser")
def open_in_clean_browser(job_id: int):
    """Open the offer in a fresh, headed Chromium window (clean session).

    For portals (e.g. Computrabajo) whose anti-bot blocks the user's main
    browser; a clean profile loads fine. Launches a detached process so the
    browser window survives this request.
    """
    session = get_session()
    job = JobRepo(session).get_by_id(job_id)
    session.close()
    if not job or not job.url:
        raise HTTPException(status_code=404, detail="Empleo no encontrado")

    from src.automation.open_offer import open_incognito

    if not open_incognito(job.url):
        raise HTTPException(
            status_code=500,
            detail="No se encontró Chrome/Edge/Brave para abrir en modo incógnito.",
        )
    return {"ok": True}


@router.post("/search")
def search_jobs(data: JobSearchRequest):
    criteria = SearchCriteria(
        keywords=data.keywords,
        location=data.location,
        remote=data.remote,
        platforms=data.platforms,
        posted_within_hours=data.posted_within_hours,
    )

    all_jobs = []
    for platform in data.platforms:
        scraper = _get_scraper(platform)
        if scraper:
            result = scraper.search(criteria, max_pages=data.pages)
            all_jobs.extend(result.jobs)

    # Save to DB
    session = get_session()
    try:
        job_repo = JobRepo(session)
        saved_jobs = []
        for job in all_jobs:
            saved = job_repo.upsert(
                external_id=job.external_id,
                platform=job.platform,
                title=job.title,
                company=job.company,
                location=job.location,
                url=job.url,
                is_remote=job.is_remote,
                is_easy_apply=job.is_easy_apply,
                description=job.description,
            )
            saved_jobs.append(saved)

        # Mark ONLY this search's results as the current "found" set, so the
        # Empleos list refreshes instead of accumulating old searches.
        session.query(Job).filter(Job.from_last_search.is_(True)).update(
            {Job.from_last_search: False}
        )
        ids = [j.id for j in saved_jobs]
        if ids:
            session.query(Job).filter(Job.id.in_(ids)).update(
                {Job.from_last_search: True}, synchronize_session=False
            )

        SearchHistoryRepo(session).save(
            criteria.model_dump(), ",".join(data.platforms), len(all_jobs)
        )
        # Serialise while the session is still open; otherwise the ORM objects
        # become detached and raise DetachedInstanceError.
        response = {
            "total": len(all_jobs),
            "jobs": [JobResponse.model_validate(j) for j in saved_jobs],
        }
    finally:
        session.close()

    return response


def _get_scraper(platform: str):
    if platform == "linkedin":
        from src.scraper.linkedin import LinkedInScraper
        return LinkedInScraper()
    elif platform == "indeed":
        from src.scraper.indeed import IndeedScraper
        return IndeedScraper()
    elif platform == "glassdoor":
        from src.scraper.glassdoor import GlassdoorScraper
        return GlassdoorScraper()
    elif platform == "computrabajo":
        from src.scraper.colombian import ComputrabajoScraper
        return ComputrabajoScraper()
    # 'elempleo' is disabled: its search is JS-rendered and its API needs auth,
    # so the server HTML returns generic (unfiltered) listings. Use jobspy/Computrabajo.
    return None
