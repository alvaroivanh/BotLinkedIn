from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.api.schemas import DashboardStats
from src.db.database import get_session
from src.db.repository import ApplicationRepo, JobRepo, LetterRepo

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent.parent / "web" / "templates"))


@router.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request):
    session = get_session()
    stats = _get_stats(session)
    session.close()
    return templates.TemplateResponse("dashboard.html", {"request": request, "stats": stats})


@router.get("/applications", response_class=HTMLResponse)
def applications_page(request: Request):
    session = get_session()
    apps = ApplicationRepo(session).list_all()
    session.close()
    return templates.TemplateResponse("applications.html", {"request": request, "applications": apps})


@router.get("/jobs", response_class=HTMLResponse)
def jobs_page(request: Request):
    session = get_session()
    jobs = JobRepo(session).list_all(limit=50)
    session.close()
    return templates.TemplateResponse("jobs.html", {"request": request, "jobs": jobs})


@router.get("/letters", response_class=HTMLResponse)
def letters_page(request: Request):
    session = get_session()
    letters = LetterRepo(session).list_all()
    session.close()
    return templates.TemplateResponse("letters.html", {"request": request, "letters": letters})


@router.get("/api/dashboard", response_model=DashboardStats)
def dashboard_stats():
    session = get_session()
    stats = _get_stats(session)
    session.close()
    return stats


def _get_stats(session) -> DashboardStats:
    app_repo = ApplicationRepo(session)
    raw_stats = app_repo.get_stats()
    return DashboardStats(
        total_applications=raw_stats.get("total", 0),
        applied=raw_stats.get("applied", 0),
        pending=raw_stats.get("pending", 0),
        interview=raw_stats.get("interview", 0),
        offer=raw_stats.get("offer", 0),
        rejected=raw_stats.get("rejected", 0),
        total_jobs=len(JobRepo(session).list_all(limit=99999)),
        total_letters=len(LetterRepo(session).list_all()),
        applications_today=app_repo.count_today(),
    )
