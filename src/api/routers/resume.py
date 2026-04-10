import shutil

from fastapi import APIRouter, HTTPException, UploadFile

from src.config import settings
from src.db.database import get_session
from src.db.repository import ResumeRepo

router = APIRouter()


@router.get("/")
def get_resume():
    session = get_session()
    data = ResumeRepo(session).get_parsed_data()
    session.close()
    if not data:
        raise HTTPException(status_code=404, detail="No resume found")
    return data


@router.post("/upload")
async def upload_resume(file: UploadFile, use_ai: bool = True):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Save file
    dest = settings.resumes_dir / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Parse
    from src.cv.extractor import extract_resume
    from src.cv.parser import extract_text

    text = extract_text(dest)
    resume_data = extract_resume(text, use_ai=use_ai)

    # Save to DB
    session = get_session()
    ResumeRepo(session).save(str(dest), resume_data.model_dump())
    session.close()

    return {"message": "Resume uploaded and parsed successfully", "data": resume_data.model_dump()}
