"""Conversational assistant (Claude) for the dashboard.

Exposes a chat page (`GET /chat`) and a JSON endpoint (`POST /api/chat`) that
runs Claude with tool-use so the assistant can actually search jobs, check the
resume, review application status and generate cover letters on request.
"""
import json
from pathlib import Path

import anthropic
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.config import settings
from src.db.database import get_session
from src.db.repository import ApplicationRepo, JobRepo, LetterRepo, ResumeRepo, SearchHistoryRepo

router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent.parent / "web" / "templates")
)


# ── Page ──────────────────────────────────────────────────────

@router.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request):
    return templates.TemplateResponse(request, "chat.html", {})


# ── Chat API ──────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


def _load_soul() -> str:
    """Load the assistant persona ("soul") from src/ai/soul.md (editable)."""
    soul_path = Path(__file__).resolve().parent.parent.parent / "ai" / "soul.md"
    try:
        return soul_path.read_text(encoding="utf-8").strip()
    except OSError:
        # Fallback persona if the file is missing.
        return (
            "Eres Alex, un reclutador y headhunter experto que ayuda al candidato "
            "a conseguir el mejor empleo posible. Hablas en español, claro y conciso."
        )


# Operational rules (tools, constraints) appended after the persona so the soul
# can be edited freely in soul.md without breaking tool behavior.
_OPERATIONAL_RULES = """

---
## Herramientas y reglas operativas
Como asistente de BotLinkedIn puedes ejecutar acciones reales con estas herramientas:
- get_resume: revisar los datos de la hoja de vida ya cargada.
- search_jobs: buscar empleos en LinkedIn, Indeed o Glassdoor.
- list_saved_jobs: listar los empleos guardados.
- application_status: ver el estado de las postulaciones.
- generate_cover_letter: generar una carta de presentación para un empleo (por su ID).

Reglas:
- Usa las herramientas cuando el usuario pida una acción concreta; no inventes resultados.
- Para SUBIR la hoja de vida, el usuario debe usar el clip 📎 (solo PDF); no puedes \
recibir el archivo por texto. Si te lo piden, indícale que use ese botón.
- Si una herramienta devuelve un error, explícalo en lenguaje sencillo y sugiere cómo \
resolverlo (por ejemplo, configurar credenciales)."""


SYSTEM_PROMPT = _load_soul() + _OPERATIONAL_RULES


TOOLS = [
    {
        "name": "get_resume",
        "description": "Devuelve los datos estructurados de la hoja de vida actualmente cargada.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_jobs",
        "description": "Busca empleos en las plataformas indicadas y los guarda en la base de datos.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keywords": {"type": "string", "description": "Palabras clave del cargo, p. ej. 'desarrollador python'"},
                "location": {"type": "string", "description": "Ubicación, p. ej. 'Bogotá'. Vacío para cualquiera."},
                "remote": {"type": "boolean", "description": "Solo empleos remotos"},
                "platforms": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["linkedin", "indeed", "glassdoor"]},
                    "description": "Plataformas donde buscar",
                },
            },
            "required": ["keywords"],
        },
    },
    {
        "name": "list_saved_jobs",
        "description": "Lista los empleos ya guardados en la base de datos.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Cuántos mostrar (máx. 30)"},
            },
        },
    },
    {
        "name": "application_status",
        "description": "Resumen del estado de las postulaciones (enviadas, pendientes, entrevistas, etc.).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "generate_cover_letter",
        "description": "Genera una carta de presentación para un empleo guardado, identificado por su ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "integer", "description": "ID del empleo en la base de datos"},
                "tone": {"type": "string", "enum": ["formal", "conversational", "technical"]},
            },
            "required": ["job_id"],
        },
    },
]


# ── Tool implementations ──────────────────────────────────────

def _tool_get_resume() -> dict:
    session = get_session()
    try:
        data = ResumeRepo(session).get_parsed_data()
    finally:
        session.close()
    if not data:
        return {"error": "No hay ninguna hoja de vida cargada. Adjunta tu CV en PDF con el clip 📎."}
    # Trim heavy fields so the model gets a compact summary.
    summary = {
        "name": data.get("name"),
        "email": data.get("email"),
        "phone": data.get("phone"),
        "skills": [s.get("name") if isinstance(s, dict) else s for s in (data.get("skills") or [])][:20],
        "experience_count": len(data.get("experiences") or []),
        "education_count": len(data.get("education") or []),
        "languages": data.get("languages"),
    }
    return summary


def _tool_search_jobs(keywords: str, location: str = "", remote: bool = False,
                      platforms: list[str] | None = None) -> dict:
    from src.api.routers.jobs import _get_scraper
    from src.scraper.models import SearchCriteria

    platforms = platforms or ["linkedin", "indeed"]
    criteria = SearchCriteria(keywords=keywords, location=location, remote=remote, platforms=platforms)

    all_jobs = []
    errors = []
    for platform in platforms:
        scraper = _get_scraper(platform)
        if not scraper:
            continue
        try:
            result = scraper.search(criteria, max_pages=2)
            all_jobs.extend(result.jobs)
        except Exception as exc:  # noqa: BLE001 - report scraper failure to the model
            errors.append(f"{platform}: {exc}")

    session = get_session()
    try:
        job_repo = JobRepo(session)
        saved = []
        for job in all_jobs:
            row = job_repo.upsert(
                external_id=job.external_id,
                platform=job.platform,
                title=job.title,
                company=job.company,
                location=job.location,
                url=job.url,
                is_remote=job.is_remote,
                is_easy_apply=job.is_easy_apply,
                description=job.description,
            )
            saved.append({"id": row.id, "title": row.title, "company": row.company,
                          "location": row.location, "platform": row.platform})
        SearchHistoryRepo(session).save(criteria.model_dump(), ",".join(platforms), len(all_jobs))
    finally:
        session.close()

    out = {"total_found": len(all_jobs), "jobs": saved[:15]}
    if errors:
        out["errors"] = errors
    return out


def _tool_list_saved_jobs(limit: int = 15) -> dict:
    limit = max(1, min(limit, 30))
    session = get_session()
    try:
        jobs = JobRepo(session).list_all(limit=limit)
        rows = [{"id": j.id, "title": j.title, "company": j.company,
                 "location": j.location, "platform": j.platform,
                 "easy_apply": j.is_easy_apply} for j in jobs]
    finally:
        session.close()
    return {"count": len(rows), "jobs": rows}


def _tool_application_status() -> dict:
    session = get_session()
    try:
        return ApplicationRepo(session).get_stats()
    finally:
        session.close()


def _tool_generate_cover_letter(job_id: int, tone: str = "formal") -> dict:
    from src.ai.cover_letter import generate_cover_letter
    from src.cv.models import ResumeData
    from src.scraper.models import JobPosting

    session = get_session()
    try:
        job = JobRepo(session).get_by_id(job_id)
        if not job:
            return {"error": f"No existe un empleo con ID {job_id}."}
        resume_data = ResumeRepo(session).get_parsed_data()
        if not resume_data:
            return {"error": "No hay hoja de vida cargada. Adjunta tu CV en PDF primero."}
        job_posting = JobPosting(
            title=job.title, company=job.company, location=job.location or "",
            description=job.description or "", url=job.url,
        )
    finally:
        session.close()

    resume = ResumeData(**resume_data)
    letter_text, tokens = generate_cover_letter(resume, job_posting, tone=tone)

    session = get_session()
    try:
        LetterRepo(session).save(letter_type="cover", content=letter_text,
                                 model_used=settings.claude_model, tokens_used=tokens, tone=tone)
    finally:
        session.close()
    return {"job": f"{job.title} en {job.company}", "tone": tone, "letter": letter_text}


TOOL_IMPL = {
    "get_resume": _tool_get_resume,
    "search_jobs": _tool_search_jobs,
    "list_saved_jobs": _tool_list_saved_jobs,
    "application_status": _tool_application_status,
    "generate_cover_letter": _tool_generate_cover_letter,
}


def _run_tool(name: str, args: dict) -> str:
    try:
        result = TOOL_IMPL[name](**args)
    except Exception as exc:  # noqa: BLE001 - surface any failure back to the model
        result = {"error": f"La herramienta '{name}' falló: {exc}"}
    return json.dumps(result, ensure_ascii=False, default=str)


@router.post("/api/chat")
def chat(req: ChatRequest):
    # Route to the OpenRouter (OpenAI-compatible) tool-calling loop when that
    # backend is selected; otherwise use the Anthropic tool-use loop.
    if settings.ai_backend == "openrouter":
        if not settings.openrouter_api_key:
            return {"reply": "⚠️ No hay OPENROUTER_API_KEY configurada en el archivo .env, "
                             "así que no puedo responder. Agrégala y reinicia el bot."}
        return _chat_openrouter(req)

    if not settings.anthropic_api_key:
        return {"reply": "⚠️ No hay ANTHROPIC_API_KEY configurada en el archivo .env, "
                         "así que no puedo responder. Agrégala y reinicia el bot."}

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    actions: list[str] = []
    for _ in range(6):  # safety cap on tool-use rounds
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            text = "".join(b.text for b in response.content if b.type == "text")
            return {"reply": text or "(sin respuesta)", "actions": actions}

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                actions.append(block.name)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": _run_tool(block.name, block.input or {}),
                })
        messages.append({"role": "user", "content": tool_results})

    return {"reply": "Se alcanzó el límite de pasos del asistente. Intenta reformular tu pedido.",
            "actions": actions}


# ── OpenRouter (OpenAI-compatible) tool-calling loop ──────────

def _tools_openai() -> list[dict]:
    """Convert the Anthropic-format TOOLS into OpenAI/OpenRouter function tools."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        for t in TOOLS
    ]


def _chat_openrouter(req: ChatRequest) -> dict:
    import httpx

    from src.ai.openrouter_client import OPENROUTER_URL

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/alvaroivanh/BotLinkedIn",
        "X-Title": "BotLinkedIn",
    }
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += [{"role": m.role, "content": m.content} for m in req.messages]
    tools = _tools_openai()

    actions: list[str] = []
    for _ in range(6):  # safety cap on tool-call rounds
        body = {
            "model": settings.openrouter_model,
            "max_tokens": 2048,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
        }
        resp = httpx.post(OPENROUTER_URL, headers=headers, json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            return {"reply": f"⚠️ Error de OpenRouter: {data['error']}", "actions": actions}

        msg = data["choices"][0]["message"]
        tool_calls = msg.get("tool_calls")

        if not tool_calls:
            return {"reply": msg.get("content") or "(sin respuesta)", "actions": actions}

        # Echo the assistant turn (with its tool calls) back into the history.
        messages.append({
            "role": "assistant",
            "content": msg.get("content"),
            "tool_calls": tool_calls,
        })
        for call in tool_calls:
            fn = call.get("function", {})
            # Some models (e.g. Gemini) namespace the function as "default_api.<name>".
            name = fn.get("name", "").split(".")[-1]
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            actions.append(name)
            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id"),
                "content": _run_tool(name, args),
            })

    return {"reply": "Se alcanzó el límite de pasos del asistente. Intenta reformular tu pedido.",
            "actions": actions}
