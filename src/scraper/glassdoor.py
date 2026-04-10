import hashlib
import logging
import time

import httpx
from bs4 import BeautifulSoup

from src.scraper.base import BaseScraper
from src.scraper.models import JobPosting, SearchCriteria, SearchResult

logger = logging.getLogger(__name__)

GLASSDOOR_BASE = "https://www.glassdoor.com/Job/jobs.htm"


class GlassdoorScraper(BaseScraper):
    """Glassdoor job scraper using public web pages."""

    def __init__(self):
        self.client = httpx.Client(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=30,
            follow_redirects=True,
        )
        self.delay = 3

    def search(self, criteria: SearchCriteria, max_pages: int = 2) -> SearchResult:
        jobs: list[JobPosting] = []

        for page in range(max_pages):
            params = {
                "sc.keyword": criteria.keywords,
                "locT": "C",
                "locKeyword": criteria.location,
                "p": page + 1,
            }
            if criteria.remote:
                params["remoteWorkType"] = "1"

            try:
                response = self.client.get(GLASSDOOR_BASE, params=params)
                if response.status_code != 200:
                    logger.warning(f"Glassdoor returned {response.status_code}")
                    break

                page_jobs = self._parse_results(response.text)
                if not page_jobs:
                    break

                jobs.extend(page_jobs)
                logger.info(f"Glassdoor page {page + 1}: found {len(page_jobs)} jobs")

                if page < max_pages - 1:
                    time.sleep(self.delay)

            except Exception as e:
                logger.error(f"Glassdoor scraping error: {e}")
                break

        return SearchResult(
            jobs=jobs,
            total_found=len(jobs),
            search_criteria=criteria,
        )

    def get_details(self, job_url: str) -> JobPosting | None:
        try:
            response = self.client.get(job_url)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")
            desc_div = soup.find("div", class_="desc")

            return JobPosting(
                external_id=hashlib.md5(job_url.encode()).hexdigest()[:12],
                platform="glassdoor",
                description=desc_div.get_text(strip=True) if desc_div else "",
                url=job_url,
            )
        except Exception as e:
            logger.error(f"Error getting Glassdoor job details: {e}")
            return None

    def _parse_results(self, html: str) -> list[JobPosting]:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all("li", class_="react-job-listing")
        jobs = []

        for card in cards:
            try:
                title_tag = card.find("a", class_="jobLink")
                company_tag = card.find("div", class_="jobEmpolyerName") or card.find(
                    "span", class_="EmployerProfile_compactEmployerName"
                )
                location_tag = card.find("span", class_="loc") or card.find(
                    "div", attrs={"data-test": "emp-location"}
                )

                title = title_tag.get_text(strip=True) if title_tag else ""
                url = ""
                if title_tag and title_tag.get("href"):
                    href = title_tag["href"]
                    url = f"https://www.glassdoor.com{href}" if not href.startswith("http") else href

                job_id = card.get("data-id", "") or card.get("data-job-id", "")
                external_id = job_id or hashlib.md5(title.encode()).hexdigest()[:12]

                job = JobPosting(
                    external_id=str(external_id),
                    platform="glassdoor",
                    title=title,
                    company=company_tag.get_text(strip=True) if company_tag else "",
                    location=location_tag.get_text(strip=True) if location_tag else "",
                    url=url,
                )
                if job.title:
                    jobs.append(job)
            except Exception as e:
                logger.debug(f"Error parsing Glassdoor card: {e}")
                continue

        return jobs
