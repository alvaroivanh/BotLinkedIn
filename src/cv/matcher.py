"""Heuristic match between a parsed resume and a job posting.

No AI / no cost: uses fuzzy string matching (thefuzz/rapidfuzz) to estimate how
well the candidate's profile fits a job. Returns a 0-100 percentage.
"""

from thefuzz import fuzz


def _profile_text(resume: dict) -> str:
    parts = [resume.get("summary", "")]
    parts += [s.get("name", "") for s in (resume.get("skills") or [])]
    parts += [e.get("title", "") for e in (resume.get("experiences") or [])]
    parts += (resume.get("languages") or [])
    return " ".join(p for p in parts if p)


def match_score(resume: dict, title: str, description: str = "") -> int:
    """Estimate 0-100 how well the resume fits the job (title + description)."""
    if not resume:
        return 0
    profile = _profile_text(resume).lower().strip()
    job = ((title or "") + " " + (description or "")).lower().strip()
    if not profile or not job:
        return 0

    # Overall fuzzy similarity (token_set handles very different lengths).
    sim = fuzz.token_set_ratio(profile, job)

    # Skill coverage: fraction of resume skills that appear in the job text.
    skills = [s.get("name", "").lower() for s in (resume.get("skills") or []) if s.get("name")]
    coverage = 0.0
    if skills:
        present = sum(1 for s in skills if fuzz.partial_ratio(s, job) >= 82)
        coverage = present / len(skills)

    # Title relevance: best resume experience title vs the job title.
    titles = [e.get("title", "").lower() for e in (resume.get("experiences") or []) if e.get("title")]
    title_sim = max((fuzz.token_set_ratio(t, (title or "").lower()) for t in titles), default=0)

    score = 0.40 * sim + 0.30 * (coverage * 100) + 0.30 * title_sim
    return int(round(min(100, max(0, score))))
