import asyncio
import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.config import settings

# Force UTF-8 console output. Windows consoles default to cp1252, which makes
# rich crash when printing accents or box-drawing characters (e.g. in letters).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

app = typer.Typer(name="botlinkedin", help="AI-powered job application automation agent")
console = Console()

# ── Sub-commands ──────────────────────────────────────────────

resume_app = typer.Typer(help="Resume/CV management")
search_app = typer.Typer(help="Job search across platforms")
apply_app = typer.Typer(help="Apply to jobs")
letter_app = typer.Typer(help="Generate cover/reference letters")
dashboard_app = typer.Typer(help="Web dashboard")

app.add_typer(resume_app, name="resume")
app.add_typer(search_app, name="search")
app.add_typer(apply_app, name="apply")
app.add_typer(letter_app, name="letter")
app.add_typer(dashboard_app, name="dashboard")


# ── Resume commands ───────────────────────────────────────────

@resume_app.command("parse")
def resume_parse(
    pdf_path: str = typer.Argument(..., help="Path to PDF resume"),
    use_ai: bool = typer.Option(True, help="Use Claude AI for enhanced extraction"),
):
    """Parse a PDF resume and save structured data."""
    from src.cv.extractor import extract_resume
    from src.cv.parser import extract_text
    from src.db.database import init_db
    from src.db.repository import ResumeRepo

    init_db()
    console.print(f"[bold]Parsing resume:[/bold] {pdf_path}")

    text = extract_text(Path(pdf_path))
    console.print(f"[green]Extracted {len(text)} characters from PDF[/green]")

    resume_data = extract_resume(text, use_ai=use_ai)

    # Save to database
    repo = ResumeRepo()
    repo.save(pdf_path, resume_data.model_dump())

    # Display results
    table = Table(title="Resume Data")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Name", resume_data.name)
    table.add_row("Email", resume_data.email)
    table.add_row("Phone", resume_data.phone)
    table.add_row("LinkedIn", resume_data.linkedin_url)
    table.add_row("Skills", ", ".join(s.name for s in resume_data.skills[:10]))
    table.add_row("Experience", str(len(resume_data.experiences)) + " positions")
    table.add_row("Education", str(len(resume_data.education)) + " entries")
    table.add_row("Languages", ", ".join(resume_data.languages))
    console.print(table)


@resume_app.command("show")
def resume_show():
    """Display the current active resume data."""
    from src.db.database import init_db
    from src.db.repository import ResumeRepo

    init_db()
    repo = ResumeRepo()
    data = repo.get_parsed_data()

    if not data:
        console.print("[red]No resume found. Use 'botlinkedin resume parse <pdf>' first.[/red]")
        raise typer.Exit(1)

    console.print_json(json.dumps(data, indent=2, default=str))


# ── Search commands ───────────────────────────────────────────

@search_app.command("run")
def search_run(
    keywords: str = typer.Option(..., "--keywords", "-k", help="Search keywords"),
    location: str = typer.Option("", "--location", "-l", help="Location filter"),
    platform: str = typer.Option(
        "linkedin,indeed", "--platform", "-p", help="Platforms: linkedin,indeed,glassdoor"
    ),
    remote: bool = typer.Option(False, "--remote", "-r", help="Remote jobs only"),
    pages: int = typer.Option(2, "--pages", help="Number of pages to scrape"),
):
    """Search for jobs across platforms."""
    from src.db.database import init_db
    from src.db.repository import JobRepo, SearchHistoryRepo
    from src.scraper.models import SearchCriteria

    init_db()
    platforms = [p.strip() for p in platform.split(",")]
    criteria = SearchCriteria(
        keywords=keywords,
        location=location,
        remote=remote,
        platforms=platforms,
    )

    all_jobs = []

    for plat in platforms:
        console.print(f"[bold]Searching {plat}...[/bold]")
        scraper = _get_scraper(plat)
        if scraper:
            result = scraper.search(criteria, max_pages=pages)
            all_jobs.extend(result.jobs)
            console.print(f"  [green]Found {len(result.jobs)} jobs on {plat}[/green]")

    # Save to database
    job_repo = JobRepo()
    for job in all_jobs:
        job_repo.upsert(
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

    # Save search history
    SearchHistoryRepo().save(criteria.model_dump(), platform, len(all_jobs))

    # Display results
    table = Table(title=f"Job Search Results ({len(all_jobs)} total)")
    table.add_column("ID", style="dim")
    table.add_column("Platform", style="cyan")
    table.add_column("Title", style="bold")
    table.add_column("Company", style="green")
    table.add_column("Location")
    table.add_column("Easy Apply", style="yellow")

    for i, job in enumerate(all_jobs[:30], 1):
        table.add_row(
            str(i),
            job.platform,
            job.title[:40],
            job.company[:25],
            job.location[:20],
            "Yes" if job.is_easy_apply else "No",
        )

    console.print(table)


@search_app.command("results")
def search_results(limit: int = typer.Option(20, help="Number of results to show")):
    """Show recent search results from the database."""
    from src.db.database import init_db
    from src.db.repository import JobRepo

    init_db()
    jobs = JobRepo().list_all(limit=limit)

    table = Table(title=f"Saved Jobs ({len(jobs)})")
    table.add_column("DB ID", style="dim")
    table.add_column("Platform", style="cyan")
    table.add_column("Title", style="bold")
    table.add_column("Company", style="green")
    table.add_column("Location")

    for job in jobs:
        table.add_row(str(job.id), job.platform, job.title[:40], job.company[:25], (job.location or "")[:20])

    console.print(table)


# ── Apply commands ────────────────────────────────────────────

@apply_app.command("job")
def apply_job(
    job_id: int = typer.Argument(..., help="Database job ID to apply to"),
    headless: bool = typer.Option(False, help="Run browser in headless mode"),
):
    """Apply to a single job by its database ID."""
    from src.cv.models import ResumeData
    from src.db.database import init_db
    from src.db.repository import ApplicationRepo, JobRepo, ResumeRepo

    init_db()

    job = JobRepo().get_by_id(job_id)
    if not job:
        console.print(f"[red]Job ID {job_id} not found[/red]")
        raise typer.Exit(1)

    resume_data = ResumeRepo().get_parsed_data()
    if not resume_data:
        console.print("[red]No resume found. Parse one first.[/red]")
        raise typer.Exit(1)

    resume = ResumeData(**resume_data)
    active_resume = ResumeRepo().get_active()

    console.print(f"[bold]Applying to:[/bold] {job.title} at {job.company}")
    console.print(f"[dim]URL: {job.url}[/dim]")

    # Create application record
    app_record = ApplicationRepo().create(job_id=job.id, resume_id=active_resume.id)

    from src.automation.linkedin_apply import apply_to_job

    result = asyncio.run(
        apply_to_job(
            job_url=job.url,
            resume=resume,
            resume_pdf_path=active_resume.file_path,
            headless=headless,
        )
    )

    if result["success"]:
        ApplicationRepo().update_status(app_record.id, "applied")
        console.print("[bold green]Application submitted successfully![/bold green]")
    else:
        ApplicationRepo().update_status(app_record.id, "pending", error_log=result["message"])
        console.print(f"[red]Application failed: {result['message']}[/red]")


@apply_app.command("status")
def apply_status():
    """Show application status summary."""
    from src.db.database import init_db
    from src.db.repository import ApplicationRepo

    init_db()
    stats = ApplicationRepo().get_stats()

    table = Table(title="Application Status")
    table.add_column("Status", style="cyan")
    table.add_column("Count", style="bold")

    for status, count in stats.items():
        style = {
            "applied": "green",
            "pending": "yellow",
            "interview": "blue",
            "offer": "bold green",
            "rejected": "red",
            "total": "bold",
        }.get(status, "white")
        table.add_row(status.capitalize(), f"[{style}]{count}[/{style}]")

    console.print(table)


# ── Letter commands ───────────────────────────────────────────

@letter_app.command("cover")
def letter_cover(
    job_id: int = typer.Argument(..., help="Database job ID"),
    tone: str = typer.Option("formal", help="Tone: formal, conversational, technical"),
    output: str = typer.Option("", help="Output file path (PDF). Leave empty for console output."),
):
    """Generate a cover letter for a specific job."""
    from src.ai.cover_letter import generate_cover_letter, save_cover_letter_pdf
    from src.cv.models import ResumeData
    from src.db.database import init_db
    from src.db.repository import JobRepo, LetterRepo, ResumeRepo
    from src.scraper.models import JobPosting

    init_db()

    job = JobRepo().get_by_id(job_id)
    if not job:
        console.print(f"[red]Job ID {job_id} not found[/red]")
        raise typer.Exit(1)

    resume_data = ResumeRepo().get_parsed_data()
    if not resume_data:
        console.print("[red]No resume found. Parse one first.[/red]")
        raise typer.Exit(1)

    resume = ResumeData(**resume_data)
    job_posting = JobPosting(
        title=job.title,
        company=job.company,
        location=job.location or "",
        description=job.description or "",
        url=job.url,
    )

    console.print(f"[bold]Generating cover letter for:[/bold] {job.title} at {job.company}")

    letter_text, tokens = generate_cover_letter(resume, job_posting, tone=tone)

    # Save to database
    LetterRepo().save(
        letter_type="cover",
        content=letter_text,
        model_used=settings.claude_model,
        tokens_used=tokens,
    )

    if output:
        save_cover_letter_pdf(letter_text, output)
        console.print(f"[green]Cover letter saved to: {output}[/green]")
    else:
        console.print("\n[bold cyan]── Cover Letter ──[/bold cyan]\n")
        console.print(letter_text)

    console.print(f"\n[dim]Tokens used: {tokens}[/dim]")


@letter_app.command("reference")
def letter_reference(
    recommender: str = typer.Option(..., "--recommender", "-r", help="Recommender's name"),
    relationship: str = typer.Option(
        ..., "--relationship", help="Relationship (e.g., 'Direct supervisor at Company X')"
    ),
    qualities: str = typer.Option("", help="Qualities to highlight"),
    purpose: str = typer.Option("General professional reference", help="Purpose of the letter"),
    output: str = typer.Option("", help="Output file path (PDF)"),
):
    """Generate a reference/recommendation letter."""
    from src.ai.cover_letter import save_cover_letter_pdf
    from src.ai.reference_letter import generate_reference_letter
    from src.cv.models import ResumeData
    from src.db.database import init_db
    from src.db.repository import LetterRepo, ResumeRepo

    init_db()

    resume_data = ResumeRepo().get_parsed_data()
    if not resume_data:
        console.print("[red]No resume found. Parse one first.[/red]")
        raise typer.Exit(1)

    resume = ResumeData(**resume_data)

    console.print(f"[bold]Generating reference letter from:[/bold] {recommender}")

    letter_text, tokens = generate_reference_letter(
        resume, recommender, relationship, qualities, purpose
    )

    LetterRepo().save(
        letter_type="reference",
        content=letter_text,
        model_used=settings.claude_model,
        tokens_used=tokens,
    )

    if output:
        save_cover_letter_pdf(letter_text, output)
        console.print(f"[green]Reference letter saved to: {output}[/green]")
    else:
        console.print("\n[bold cyan]── Reference Letter ──[/bold cyan]\n")
        console.print(letter_text)

    console.print(f"\n[dim]Tokens used: {tokens}[/dim]")


@letter_app.command("list")
def letter_list(
    letter_type: str = typer.Option("", help="Filter by type: cover, reference"),
):
    """List generated letters."""
    from src.db.database import init_db
    from src.db.repository import LetterRepo

    init_db()
    letters = LetterRepo().list_all(letter_type=letter_type or None)

    table = Table(title=f"Generated Letters ({len(letters)})")
    table.add_column("ID", style="dim")
    table.add_column("Type", style="cyan")
    table.add_column("Tone")
    table.add_column("Model")
    table.add_column("Tokens", style="dim")
    table.add_column("Created", style="dim")

    for letter in letters:
        table.add_row(
            str(letter.id),
            letter.letter_type,
            letter.tone,
            letter.model_used,
            str(letter.tokens_used or ""),
            str(letter.created_at)[:16],
        )

    console.print(table)


# ── Dashboard ─────────────────────────────────────────────────

@dashboard_app.command("start")
def dashboard_start(
    port: int = typer.Option(settings.dashboard_port, help="Server port"),
    host: str = typer.Option(settings.dashboard_host, help="Server host"),
):
    """Start the web dashboard."""
    import uvicorn

    from src.db.database import init_db

    init_db()
    console.print(f"[bold green]Starting dashboard at http://{host}:{port}[/bold green]")
    uvicorn.run("src.api.app:app", host=host, port=port, reload=True)


# ── Helpers ───────────────────────────────────────────────────

def _get_scraper(platform: str):
    if platform == "linkedin":
        from src.scraper.linkedin import LinkedInScraper
        return LinkedInScraper()
    elif platform == "indeed":
        from src.scraper.indeed import IndeedScraper
        return IndeedScraper()
    elif platform == "glassdoor":
        from src.scraper.glassdoor import GlassdoorScraper
        return GlassdoorScraper()
    else:
        console.print(f"[yellow]Unknown platform: {platform}[/yellow]")
        return None


# ── Init DB on startup ───────────────────────────────────────

@app.callback()
def main():
    """BotLinkedIn - AI-powered job application automation."""
    pass


if __name__ == "__main__":
    app()
