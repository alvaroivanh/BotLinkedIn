from fastapi import APIRouter

from src.config import settings
from src.db.database import get_session
from src.db.repository import FormAnswerRepo
from src.api.schemas import FormAnswerRequest

router = APIRouter()


@router.get("/")
def get_settings():
    return {
        "claude_model": settings.claude_model,
        "max_daily_applications": settings.max_daily_applications,
        "delay_min": settings.delay_min,
        "delay_max": settings.delay_max,
        "applications_per_session": settings.applications_per_session,
        "dashboard_host": settings.dashboard_host,
        "dashboard_port": settings.dashboard_port,
        "log_level": settings.log_level,
        "has_api_key": bool(settings.anthropic_api_key),
        "has_linkedin_credentials": bool(settings.linkedin_email),
    }


@router.get("/answers")
def get_form_answers():
    session = get_session()
    from src.db.models import FormAnswer
    answers = session.query(FormAnswer).all()
    result = [
        {"id": a.id, "question": a.question_pattern, "answer": a.answer, "source": a.source, "times_used": a.times_used}
        for a in answers
    ]
    session.close()
    return result


@router.post("/answers")
def save_form_answer(data: FormAnswerRequest):
    session = get_session()
    fa = FormAnswerRepo(session).save_answer(data.question, data.answer, source="manual")
    session.close()
    return {"id": fa.id, "question": fa.question_pattern, "answer": fa.answer}


@router.post("/test-claude")
def test_claude():
    try:
        from src.ai.client import get_client
        client = get_client()
        response = client.generate(
            system="You are a helpful assistant.",
            user="Say 'Hello! Claude API is working.' in one sentence.",
            max_tokens=50,
        )
        return {"status": "ok", "response": response}
    except Exception as e:
        return {"status": "error", "message": str(e)}
