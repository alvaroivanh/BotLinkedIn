"""Shared job scraping via python-jobspy.

The original per-site scrapers requested Indeed/LinkedIn/Glassdoor HTML directly
and got blocked (HTTP 403). ``python-jobspy`` (already a dependency) handles
those sites robustly, so every scraper delegates here through ``scrape_with_jobspy``.
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime

from src.config import settings
from src.scraper.models import JobPosting, SearchCriteria, SearchResult

logger = logging.getLogger(__name__)


def _clean(value, default=""):
    """Normalise pandas values (NaN/None) to a plain default."""
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    return value


def _num(value):
    value = _clean(value, None)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _posted(value) -> datetime | None:
    value = _clean(value, None)
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    return None


def scrape_with_jobspy(site: str, criteria: SearchCriteria, max_pages: int = 3) -> SearchResult:
    """Scrape ``site`` (linkedin/indeed/glassdoor) and map results to JobPosting."""
    from jobspy import scrape_jobs

    results_wanted = max(15, max_pages * 15)
    kwargs = {
        "site_name": [site],
        "search_term": criteria.keywords,
        "location": criteria.location,
        "results_wanted": results_wanted,
        "description_format": "markdown",
    }
    if criteria.posted_within_hours:
        kwargs["hours_old"] = criteria.posted_within_hours
    if criteria.remote:
        kwargs["is_remote"] = True
    if site in ("indeed", "glassdoor"):
        # Indeed/Glassdoor need a country hint; LinkedIn is global.
        kwargs["country_indeed"] = settings.search_country

    try:
        df = scrape_jobs(**kwargs)
    except Exception as exc:  # noqa: BLE001 - scraping is best-effort
        logger.error("jobspy error for %s: %s", site, exc)
        return SearchResult(jobs=[], total_found=0, search_criteria=criteria)

    jobs: list[JobPosting] = []
    if df is not None and len(df):
        for row in df.to_dict("records"):
            title = str(_clean(row.get("title")))
            if not title:
                continue
            jobs.append(
                JobPosting(
                    external_id=str(_clean(row.get("id")) or _clean(row.get("job_url")))[:64],
                    platform=site,
                    title=title,
                    company=str(_clean(row.get("company"))),
                    location=str(_clean(row.get("location"))),
                    url=str(_clean(row.get("job_url"))),
                    description=str(_clean(row.get("description"))),
                    job_type=str(_clean(row.get("job_type"))),
                    is_remote=bool(_clean(row.get("is_remote"), False)),
                    salary_min=_num(row.get("min_amount")),
                    salary_max=_num(row.get("max_amount")),
                    salary_currency=str(_clean(row.get("currency"))),
                    posted_date=_posted(row.get("date_posted")),
                )
            )
    logger.info("jobspy %s: %d jobs", site, len(jobs))
    return SearchResult(jobs=jobs, total_found=len(jobs), search_criteria=criteria)
