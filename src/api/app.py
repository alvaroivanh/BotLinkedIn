from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.api.routers import (
    applications,
    chat,
    dashboard,
    jobs,
    letters,
    pipeline,
    resume,
    settings as settings_router,
)
from src.db.database import init_db

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="BotLinkedIn", version="0.1.0")

# Mount static files
static_dir = WEB_DIR / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Templates
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))

# Include API routers
app.include_router(dashboard.router)
app.include_router(pipeline.router)
app.include_router(chat.router)
app.include_router(applications.router, prefix="/api/applications", tags=["applications"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(letters.router, prefix="/api/letters", tags=["letters"])
app.include_router(resume.router, prefix="/api/resume", tags=["resume"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])


@app.on_event("startup")
def startup():
    init_db()
