from fastapi import APIRouter

from src.api.schemas import ApplicationResponse, ApplicationUpdateRequest
from src.db.database import get_session
from src.db.repository import ApplicationRepo

router = APIRouter()


@router.get("/", response_model=list[ApplicationResponse])
def list_applications(status: str | None = None):
    session = get_session()
    apps = ApplicationRepo(session).list_all(status=status)
    session.close()
    return apps


@router.get("/stats")
def application_stats():
    session = get_session()
    stats = ApplicationRepo(session).get_stats()
    session.close()
    return stats


@router.get("/{app_id}", response_model=ApplicationResponse)
def get_application(app_id: int):
    session = get_session()
    app = ApplicationRepo(session).get_by_id(app_id)
    session.close()
    if not app:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Application not found")
    return app


@router.patch("/{app_id}", response_model=ApplicationResponse)
def update_application(app_id: int, data: ApplicationUpdateRequest):
    session = get_session()
    repo = ApplicationRepo(session)
    kwargs = {}
    if data.notes is not None:
        kwargs["notes"] = data.notes
    app = repo.update_status(app_id, data.status or "pending", **kwargs)
    session.close()
    if not app:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Application not found")
    return app
