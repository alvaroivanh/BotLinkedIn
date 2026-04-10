import json
import re

from src.cv.models import Education, Experience, ResumeData, Skill


def extract_email(text: str) -> str:
    match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    return match.group(0) if match else ""


def extract_phone(text: str) -> str:
    match = re.search(r"[\+]?[\d\s\-\(\)]{7,15}", text)
    return match.group(0).strip() if match else ""


def extract_linkedin_url(text: str) -> str:
    match = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+", text)
    return match.group(0) if match else ""


def extract_name(text: str) -> str:
    """Heuristic: the first non-empty line is usually the name."""
    for line in text.split("\n"):
        line = line.strip()
        if line and len(line) < 60 and not re.search(r"[@\d]", line):
            return line
    return ""


def extract_with_regex(text: str) -> ResumeData:
    """Extract structured resume data using regex heuristics."""
    return ResumeData(
        name=extract_name(text),
        email=extract_email(text),
        phone=extract_phone(text),
        linkedin_url=extract_linkedin_url(text),
        raw_text=text,
    )


def extract_with_ai(text: str, ai_client=None) -> ResumeData:
    """Extract structured resume data using Claude API for better accuracy."""
    if ai_client is None:
        from src.ai.client import get_client

        ai_client = get_client()

    prompt = f"""Analyze this resume text and extract structured data.
Return a JSON object with these fields:
- name: full name
- email: email address
- phone: phone number
- linkedin_url: LinkedIn profile URL
- summary: professional summary (2-3 sentences)
- skills: list of objects with "name" and "category" (e.g., "technical", "soft", "language")
- experiences: list of objects with "company", "title", "start_date", "end_date", "description", "location"
- education: list of objects with "institution", "degree", "field", "start_date", "end_date"
- certifications: list of certification names
- languages: list of languages spoken

Resume text:
{text}

Return ONLY valid JSON, no markdown fences."""

    response = ai_client.generate(
        system="You are a resume parser. Extract structured data from resumes. Return only valid JSON.",
        user=prompt,
        max_tokens=4000,
    )

    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        json_match = re.search(r"\{[\s\S]*\}", response)
        if json_match:
            data = json.loads(json_match.group(0))
        else:
            return extract_with_regex(text)

    return ResumeData(
        name=data.get("name", ""),
        email=data.get("email", ""),
        phone=data.get("phone", ""),
        linkedin_url=data.get("linkedin_url", ""),
        summary=data.get("summary", ""),
        skills=[Skill(**s) if isinstance(s, dict) else Skill(name=s) for s in data.get("skills", [])],
        experiences=[Experience(**e) for e in data.get("experiences", [])],
        education=[Education(**e) for e in data.get("education", [])],
        certifications=data.get("certifications", []),
        languages=data.get("languages", []),
        raw_text=text,
    )


def extract_resume(text: str, use_ai: bool = True) -> ResumeData:
    """Extract resume data, optionally enhanced with AI."""
    if use_ai:
        try:
            return extract_with_ai(text)
        except Exception:
            pass
    return extract_with_regex(text)
