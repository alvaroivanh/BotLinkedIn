from datetime import datetime

from pydantic import BaseModel


class SearchCriteria(BaseModel):
    keywords: str = ""
    location: str = ""
    job_type: str = ""  # full-time, part-time, contract, internship
    remote: bool = False
    distance_miles: int = 25
    posted_within_hours: int = 72
    min_salary: int | None = None
    platforms: list[str] = ["linkedin", "indeed"]


class JobPosting(BaseModel):
    external_id: str = ""
    platform: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = ""
    description: str = ""
    url: str = ""
    apply_url: str = ""
    job_type: str = ""
    is_remote: bool = False
    is_easy_apply: bool = False
    skills_required: list[str] = []
    posted_date: datetime | None = None


class SearchResult(BaseModel):
    jobs: list[JobPosting] = []
    total_found: int = 0
    search_criteria: SearchCriteria | None = None
    timestamp: datetime = datetime.utcnow()
