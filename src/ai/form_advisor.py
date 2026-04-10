from src.ai.client import get_client
from src.ai.prompts import FORM_ADVISOR_SYSTEM, FORM_ADVISOR_USER
from src.cv.models import ResumeData


def answer_form_question(resume: ResumeData, question: str) -> str:
    """Use Claude to answer an unknown application form question."""
    client = get_client()

    profile = f"""Name: {resume.name}
Email: {resume.email}
Phone: {resume.phone}
Summary: {resume.summary}
Skills: {', '.join(s.name for s in resume.skills)}
Experience: {'; '.join(f'{e.title} at {e.company}' for e in resume.experiences)}
Education: {'; '.join(f'{e.degree} at {e.institution}' for e in resume.education)}
Languages: {', '.join(resume.languages)}"""

    prompt = FORM_ADVISOR_USER.format(profile=profile, question=question)

    return client.generate(
        system=FORM_ADVISOR_SYSTEM,
        user=prompt,
        max_tokens=500,
    )
