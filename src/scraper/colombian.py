"""Scrapers for Colombian job boards: Computrabajo, elempleo and Magneto.

python-jobspy does not cover these sites, so we scrape their server-rendered
search pages with httpx + BeautifulSoup. Title and URL are reliable; company and
location are best-effort (their markup is noisy). Descriptions are fetched on
demand via ``get_details`` for the preview modal.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from src.scraper.base import BaseScraper
from src.scraper.models import JobPosting, SearchCriteria, SearchResult

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CO,es;q=0.9",
}


def _slug(text: str) -> str:
    text = (text or "").strip().lower()
    text = (
        text.replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    )
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def _ext_id(url: str) -> str:
    m = re.search(r"(\d{6,})", url)
    return m.group(1) if m else hashlib.md5(url.encode()).hexdigest()[:12]


def _dedupe_location(text: str) -> str:
    # Computrabajo repeats the city, e.g. "Bogotá, D.C., Bogotá, D.C.".
    parts = [p.strip() for p in (text or "").split(",") if p.strip()]
    seen: list[str] = []
    for p in parts:
        if p not in seen:
            seen.append(p)
    return ", ".join(seen)[:60]


def _clean_company(text: str) -> str:
    # elempleo prefixes the company with an icon ligature, e.g. "industryACME".
    text = (text or "").strip()
    text = re.sub(r"^(industry|location|place|business|domain|company)(?=[A-ZÁÉÍÓÚÑ])", "", text)
    return text.strip()


class _ColombianBase(BaseScraper):
    PLATFORM = ""

    def __init__(self):
        self.client = httpx.Client(
            headers=_HEADERS, timeout=30, follow_redirects=True
        )
        self.delay = 2

    def get_details(self, job_url: str) -> JobPosting | None:
        try:
            resp = self.client.get(job_url)
            if resp.status_code != 200:
                return None
            soup = BeautifulSoup(resp.text, "html.parser")
            # Try a few common description containers, then fall back to meta.
            node = (
                soup.select_one(".description-block")
                or soup.select_one("[class*=description]")
                or soup.select_one("div.boxDetail")
                or soup.select_one("article")
            )
            description = node.get_text("\n", strip=True) if node else ""
            if not description:
                meta = soup.find("meta", attrs={"name": "description"})
                description = meta.get("content", "") if meta else ""
            return JobPosting(
                external_id=_ext_id(job_url),
                platform=self.PLATFORM,
                description=description,
                url=job_url,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("%s get_details error: %s", self.PLATFORM, exc)
            return None


class ComputrabajoScraper(_ColombianBase):
    PLATFORM = "computrabajo"
    BASE = "https://co.computrabajo.com"

    def search(self, criteria: SearchCriteria, max_pages: int = 2) -> SearchResult:
        jobs: list[JobPosting] = []
        path = f"/trabajo-de-{_slug(criteria.keywords)}"
        if criteria.location:
            path += f"-en-{_slug(criteria.location)}"

        for page in range(1, max_pages + 1):
            url = self.BASE + path + (f"?p={page}" if page > 1 else "")
            try:
                resp = self.client.get(url)
                if resp.status_code != 200:
                    logger.warning("Computrabajo returned %s", resp.status_code)
                    break
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("article.box_offer")
                if not cards:
                    break
                for card in cards:
                    link = card.select_one("a.js-o-link") or card.select_one("h2 a")
                    if not link:
                        continue
                    href = link.get("href", "").split("#")[0]
                    job_url = self.BASE + href if href.startswith("/") else href
                    company = card.select_one("a.fc_base.t_ellipsis")
                    # Location is the fs16 paragraph WITHOUT the dFlex (rating) class.
                    loc = card.select_one("p.fs16.fc_base.mt5:not(.dFlex)")
                    jobs.append(
                        JobPosting(
                            external_id=_ext_id(job_url),
                            platform=self.PLATFORM,
                            title=link.get_text(strip=True),
                            company=company.get_text(strip=True) if company else "",
                            location=_dedupe_location(loc.get_text(", ", strip=True)) if loc else "",
                            url=job_url,
                            is_easy_apply="aplicar" in card.get_text().lower(),
                        )
                    )
                if page < max_pages:
                    time.sleep(self.delay)
            except Exception as exc:  # noqa: BLE001
                logger.error("Computrabajo scraping error: %s", exc)
                break

        return SearchResult(jobs=jobs, total_found=len(jobs), search_criteria=criteria)


class ElempleoScraper(_ColombianBase):
    PLATFORM = "elempleo"
    BASE = "https://www.elempleo.com"

    def search(self, criteria: SearchCriteria, max_pages: int = 1) -> SearchResult:
        jobs: list[JobPosting] = []
        seen: set[str] = set()
        url = f"{self.BASE}/co/ofertas-empleo/?Search={quote_plus(criteria.keywords)}"
        try:
            resp = self.client.get(url)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for card in soup.select("div.result-item"):
                    link = card.select_one("a[href*='/co/ofertas-trabajo/']")
                    if not link:
                        continue
                    href = link.get("href", "")
                    job_url = self.BASE + href if href.startswith("/") else href
                    if job_url in seen:
                        continue
                    seen.add(job_url)
                    company = card.select_one("[class*=company]")
                    loc = card.select_one("[class*=location], [class*=city]")
                    jobs.append(
                        JobPosting(
                            external_id=_ext_id(job_url),
                            platform=self.PLATFORM,
                            title=link.get_text(strip=True),
                            company=_clean_company(company.get_text(strip=True)) if company else "",
                            location=(loc.get_text(strip=True)[:60] if loc else ""),
                            url=job_url,
                        )
                    )
            else:
                logger.warning("elempleo returned %s", resp.status_code)
        except Exception as exc:  # noqa: BLE001
            logger.error("elempleo scraping error: %s", exc)

        return SearchResult(jobs=jobs, total_found=len(jobs), search_criteria=criteria)


# NOTE: Magneto (magneto365.com) is intentionally not implemented here. Its
# search results are rendered client-side (the server HTML only returns generic
# featured jobs regardless of the query), so scraping it would require a
# JavaScript runtime (e.g. Playwright). It can be added later as an async
# Playwright-based scraper if needed.
