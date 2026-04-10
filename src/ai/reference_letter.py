from src.ai.client import get_client
from src.ai.prompts import REFERENCE_LETTER_SYSTEM, REFERENCE_LETTER_USER
from src.cv.models import ResumeData


def generate_reference_letter(
    resume: ResumeData,
    recommender_name: str,
    relationship: str,
    qualities: str = "",
    purpose: str = "General professional reference",
) -> tuple[str, int]:
    """Generate a reference/recommendation letter. Returns (letter_text, tokens_used)."""
    client = get_client()

    skills_str = ", ".join(s.name for s in resume.skills) if resume.skills else "Various professional skills"
    exp_str = "\n".join(
        f"- {e.title} at {e.company}: {e.description}" for e in resume.experiences
    ) if resume.experiences else resume.summary or ""

    prompt = REFERENCE_LETTER_USER.format(
        name=resume.name,
        summary=resume.summary or "Experienced professional",
        skills=skills_str,
        experience=exp_str,
        recommender_name=recommender_name,
        relationship=relationship,
        qualities=qualities or "Leadership, teamwork, technical skills, dedication",
        purpose=purpose,
    )

    text, tokens = client.generate_with_usage(
        system=REFERENCE_LETTER_SYSTEM,
        user=prompt,
        max_tokens=2000,
    )
    return text, tokens
