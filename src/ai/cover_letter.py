from src.ai.client import get_client
from src.ai.prompts import COVER_LETTER_SYSTEM, COVER_LETTER_USER
from src.cv.models import ResumeData
from src.scraper.models import JobPosting


def _format_skills(resume: ResumeData) -> str:
    if not resume.skills:
        return "Not specified"
    return ", ".join(s.name for s in resume.skills)


def _format_experience(resume: ResumeData) -> str:
    if not resume.experiences:
        return resume.summary or "Not specified"
    parts = []
    for exp in resume.experiences:
        period = f"{exp.start_date} - {exp.end_date}" if exp.start_date else ""
        parts.append(f"- {exp.title} at {exp.company} {period}\n  {exp.description}")
    return "\n".join(parts)


def _format_education(resume: ResumeData) -> str:
    if not resume.education:
        return "Not specified"
    parts = []
    for edu in resume.education:
        parts.append(f"- {edu.degree} in {edu.field} - {edu.institution}")
    return "\n".join(parts)


def generate_cover_letter(
    resume: ResumeData,
    job: JobPosting,
    tone: str = "formal",
) -> tuple[str, int]:
    """Generate a personalized cover letter. Returns (letter_text, tokens_used)."""
    client = get_client()

    prompt = COVER_LETTER_USER.format(
        name=resume.name,
        email=resume.email,
        phone=resume.phone,
        summary=resume.summary or "Experienced professional",
        skills=_format_skills(resume),
        experience=_format_experience(resume),
        education=_format_education(resume),
        job_title=job.title,
        job_company=job.company,
        job_location=job.location or "Not specified",
        job_description=job.description or "Not available",
        tone=tone,
    )

    text, tokens = client.generate_with_usage(
        system=COVER_LETTER_SYSTEM,
        user=prompt,
        max_tokens=2000,
    )
    return text, tokens


def save_cover_letter_pdf(content: str, output_path: str) -> str:
    """Save cover letter as PDF."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.set_font("Helvetica", size=11)
    pdf.set_margins(25, 25, 25)

    for line in content.split("\n"):
        pdf.multi_cell(0, 6, line)
        pdf.ln(1)

    pdf.output(output_path)
    return output_path
