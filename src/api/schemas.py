from datetime import datetime

from pydantic import BaseModel


# ── Request schemas ──

class JobSearchRequest(BaseModel):
    keywords: str
    location: str = ""
    platforms: list[str] = ["linkedin", "indeed"]
    remote: bool = False
    pages: int = 2


class CoverLetterRequest(BaseModel):
    job_id: int
    tone: str = "formal"


class ReferenceLetterRequest(BaseModel):
    recommender_name: str
    relationship: str
    qualities: str = ""
    purpose: str = "General professional reference"


class ApplicationUpdateRequest(BaseModel):
    status: str | None = None
    notes: str | None = None


class FormAnswerRequest(BaseModel):
    question: str
    answer: str


# ── Response schemas ──

class JobResponse(BaseModel):
    id: int
    external_id: str
    platform: str
    title: str
    company: str
    location: str | None
    url: str
    is_remote: bool | None
    is_easy_apply: bool | None
    scraped_at: datetime | None

    class Config:
        from_attributes = True


class ApplicationResponse(BaseModel):
    id: int
    job_id: int
    resume_id: int
    status: str
    applied_at: datetime | None
    notes: str | None
    created_at: datetime | None

    class Config:
        from_attributes = True


class LetterResponse(BaseModel):
    id: int
    letter_type: str
    content: str
    tone: str
    model_used: str
    tokens_used: int | None
    created_at: datetime | None

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    total_applications: int = 0
    applied: int = 0
    pending: int = 0
    interview: int = 0
    offer: int = 0
    rejected: int = 0
    total_jobs: int = 0
    total_letters: int = 0
    applications_today: int = 0
