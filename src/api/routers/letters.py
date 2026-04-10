from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.api.schemas import CoverLetterRequest, LetterResponse, ReferenceLetterRequest
from src.config import settings
from src.db.database import get_session
from src.db.repository import JobRepo, LetterRepo, ResumeRepo

router = APIRouter()


@router.get("/", response_model=list[LetterResponse])
def list_letters(letter_type: str = ""):
    session = get_session()
    letters = LetterRepo(session).list_all(letter_type=letter_type or None)
    session.close()
    return letters


@router.get("/{letter_id}", response_model=LetterResponse)
def get_letter(letter_id: int):
    session = get_session()
    letter = LetterRepo(session).get_by_id(letter_id)
    session.close()
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")
    return letter


@router.post("/cover", response_model=LetterResponse)
def generate_cover_letter(data: CoverLetterRequest):
    from src.ai.cover_letter import generate_cover_letter as gen_cover
    from src.cv.models import ResumeData
    from src.scraper.models import JobPosting

    session = get_session()
    job = JobRepo(session).get_by_id(data.job_id)
    if not job:
        session.close()
        raise HTTPException(status_code=404, detail="Job not found")

    resume_data = ResumeRepo(session).get_parsed_data()
    if not resume_data:
        session.close()
        raise HTTPException(status_code=400, detail="No resume found. Upload one first.")

    resume = ResumeData(**resume_data)
    job_posting = JobPosting(
        title=job.title,
        company=job.company,
        location=job.location or "",
        description=job.description or "",
        url=job.url,
    )

    letter_text, tokens = gen_cover(resume, job_posting, tone=data.tone)

    letter = LetterRepo(session).save(
        letter_type="cover",
        content=letter_text,
        model_used=settings.claude_model,
        tokens_used=tokens,
    )
    session.close()
    return letter


@router.post("/reference", response_model=LetterResponse)
def generate_reference_letter(data: ReferenceLetterRequest):
    from src.ai.reference_letter import generate_reference_letter as gen_ref
    from src.cv.models import ResumeData

    session = get_session()
    resume_data = ResumeRepo(session).get_parsed_data()
    if not resume_data:
        session.close()
        raise HTTPException(status_code=400, detail="No resume found. Upload one first.")

    resume = ResumeData(**resume_data)
    letter_text, tokens = gen_ref(
        resume, data.recommender_name, data.relationship, data.qualities, data.purpose
    )

    letter = LetterRepo(session).save(
        letter_type="reference",
        content=letter_text,
        model_used=settings.claude_model,
        tokens_used=tokens,
    )
    session.close()
    return letter


@router.get("/{letter_id}/download")
def download_letter(letter_id: int):
    from src.ai.cover_letter import save_cover_letter_pdf

    session = get_session()
    letter = LetterRepo(session).get_by_id(letter_id)
    session.close()
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")

    output_path = str(settings.letters_dir / f"{letter.letter_type}_{letter_id}.pdf")
    save_cover_letter_pdf(letter.content, output_path)

    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename=f"{letter.letter_type}_letter_{letter_id}.pdf",
    )
