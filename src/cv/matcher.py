"""Match between a parsed resume and a job posting.

Two scorers:
- match_score(): fast heuristic (fuzzy string matching, no AI). Language-biased.
- ai_match_score(): semantic score via the LLM (understands ES/EN equivalence).
"""

import re

from thefuzz import fuzz


def ai_match_score(resume: dict, title: str, description: str = "") -> int | None:
    """Semantic 0-100 fit score via the LLM. Language-independent. None on error."""
    if not resume or not (title or "").strip():
        return None
    profile = _profile_text(resume)[:1800]
    job = ((title or "") + "\n" + (description or ""))[:2500]
    system = (
        "Eres un evaluador de selección experto. Calificas de 0 a 100 qué tan bien "
        "encaja el perfil del candidato con la vacante, según el SIGNIFICADO, no el "
        "idioma: un cargo en inglés equivale a su versión en español (p. ej. 'Legal "
        "Counsel' = 'Abogado/Asesor jurídico'). Considera área, seniority y funciones. "
        "Responde ÚNICAMENTE el número entero de 0 a 100, sin texto."
    )
    user = f"PERFIL DEL CANDIDATO:\n{profile}\n\nVACANTE:\n{job}\n\nNúmero 0-100:"
    try:
        from src.ai.client import get_client

        raw = get_client().generate(system=system, user=user, max_tokens=8)
        m = re.search(r"\d{1,3}", raw or "")
        if not m:
            return None
        return max(0, min(100, int(m.group(0))))
    except Exception:
        return None


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
