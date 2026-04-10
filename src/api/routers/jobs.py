from fastapi import APIRouter, HTTPException

from src.api.schemas import JobResponse, JobSearchRequest
from src.db.database import get_session
from src.db.repository import JobRepo, SearchHistoryRepo
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


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int):
    session = get_session()
    job = JobRepo(session).get_by_id(job_id)
    session.close()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/search")
def search_jobs(data: JobSearchRequest):
    criteria = SearchCriteria(
        keywords=data.keywords,
        location=data.location,
        remote=data.remote,
        platforms=data.platforms,
    )

    all_jobs = []
    for platform in data.platforms:
        scraper = _get_scraper(platform)
        if scraper:
            result = scraper.search(criteria, max_pages=data.pages)
            all_jobs.extend(result.jobs)

    # Save to DB
    session = get_session()
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

    SearchHistoryRepo(session).save(
        criteria.model_dump(), ",".join(data.platforms), len(all_jobs)
    )
    session.close()

    return {"total": len(all_jobs), "jobs": [JobResponse.model_validate(j) for j in saved_jobs]}


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
    return None
