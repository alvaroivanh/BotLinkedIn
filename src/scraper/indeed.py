import hashlib
import logging
import time

import httpx
from bs4 import BeautifulSoup

from src.scraper.base import BaseScraper
from src.scraper.models import JobPosting, SearchCriteria, SearchResult

logger = logging.getLogger(__name__)

INDEED_BASE = "https://www.indeed.com/jobs"


class IndeedScraper(BaseScraper):
    """Indeed job scraper using public web pages."""

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
        self.delay = 2

    def search(self, criteria: SearchCriteria, max_pages: int = 3) -> SearchResult:
        jobs: list[JobPosting] = []

        for page in range(max_pages):
            params = {
                "q": criteria.keywords,
                "l": criteria.location,
                "start": page * 10,
                "fromage": self._days_filter(criteria.posted_within_hours),
            }
            if criteria.remote:
                params["remotejob"] = "032b3046-06a3-4876-8dfd-474eb5e7ed11"
            if criteria.job_type:
                params["jt"] = self._job_type_code(criteria.job_type)

            try:
                response = self.client.get(INDEED_BASE, params=params)
                if response.status_code != 200:
                    logger.warning(f"Indeed returned {response.status_code}")
                    break

                page_jobs = self._parse_results(response.text)
                if not page_jobs:
                    break

                jobs.extend(page_jobs)
                logger.info(f"Indeed page {page + 1}: found {len(page_jobs)} jobs")

                if page < max_pages - 1:
                    time.sleep(self.delay)

            except Exception as e:
                logger.error(f"Indeed scraping error: {e}")
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
            desc_div = soup.find("div", id="jobDescriptionText")

            return JobPosting(
                external_id=hashlib.md5(job_url.encode()).hexdigest()[:12],
                platform="indeed",
                description=desc_div.get_text(strip=True) if desc_div else "",
                url=job_url,
            )
        except Exception as e:
            logger.error(f"Error getting Indeed job details: {e}")
            return None

    def _parse_results(self, html: str) -> list[JobPosting]:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all("div", class_="job_seen_beacon")
        jobs = []

        for card in cards:
            try:
                title_tag = card.find("h2", class_="jobTitle")
                company_tag = card.find("span", attrs={"data-testid": "company-name"})
                location_tag = card.find("div", attrs={"data-testid": "text-location"})
                link_tag = card.find("a", href=True)

                title = title_tag.get_text(strip=True) if title_tag else ""
                url = f"https://www.indeed.com{link_tag['href']}" if link_tag else ""
                jk = link_tag.get("data-jk", "") if link_tag else ""
                external_id = jk or hashlib.md5(title.encode()).hexdigest()[:12]

                job = JobPosting(
                    external_id=str(external_id),
                    platform="indeed",
                    title=title,
                    company=company_tag.get_text(strip=True) if company_tag else "",
                    location=location_tag.get_text(strip=True) if location_tag else "",
                    url=url,
                )
                if job.title:
                    jobs.append(job)
            except Exception as e:
                logger.debug(f"Error parsing Indeed card: {e}")
                continue

        return jobs

    @staticmethod
    def _days_filter(hours: int) -> str:
        days = hours // 24
        if days <= 1:
            return "1"
        elif days <= 3:
            return "3"
        elif days <= 7:
            return "7"
        elif days <= 14:
            return "14"
        return ""

    @staticmethod
    def _job_type_code(job_type: str) -> str:
        mapping = {
            "full-time": "fulltime",
            "part-time": "parttime",
            "contract": "contract",
            "internship": "internship",
            "temporary": "temporary",
        }
        return mapping.get(job_type.lower(), "")
