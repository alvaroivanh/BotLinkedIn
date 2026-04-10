import hashlib
import logging
import time

import httpx
from bs4 import BeautifulSoup

from src.scraper.base import BaseScraper
from src.scraper.models import JobPosting, SearchCriteria, SearchResult

logger = logging.getLogger(__name__)

LINKEDIN_JOBS_API = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"


class LinkedInScraper(BaseScraper):
    """LinkedIn job scraper using the guest (public) API."""

    def __init__(self):
        self.client = httpx.Client(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
            },
            timeout=30,
            follow_redirects=True,
        )
        self.delay = 3  # seconds between requests

    def search(self, criteria: SearchCriteria, max_pages: int = 3) -> SearchResult:
        jobs: list[JobPosting] = []
        page_size = 25

        for page in range(max_pages):
            start = page * page_size
            params = {
                "keywords": criteria.keywords,
                "location": criteria.location,
                "start": start,
                "f_TPR": self._time_filter(criteria.posted_within_hours),
            }
            if criteria.remote:
                params["f_WT"] = "2"  # Remote filter
            if criteria.job_type:
                params["f_JT"] = self._job_type_code(criteria.job_type)

            try:
                response = self.client.get(LINKEDIN_JOBS_API, params=params)
                if response.status_code != 200:
                    logger.warning(f"LinkedIn API returned {response.status_code}")
                    break

                page_jobs = self._parse_job_cards(response.text)
                if not page_jobs:
                    break

                jobs.extend(page_jobs)
                logger.info(f"LinkedIn page {page + 1}: found {len(page_jobs)} jobs")

                if page < max_pages - 1:
                    time.sleep(self.delay)

            except Exception as e:
                logger.error(f"LinkedIn scraping error: {e}")
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
            description_div = soup.find("div", class_="show-more-less-html__markup")
            description = description_div.get_text(strip=True) if description_div else ""

            title_tag = soup.find("h2", class_="top-card-layout__title")
            company_tag = soup.find("a", class_="topcard__org-name-link")
            location_tag = soup.find("span", class_="topcard__flavor--bullet")

            return JobPosting(
                external_id=hashlib.md5(job_url.encode()).hexdigest()[:12],
                platform="linkedin",
                title=title_tag.get_text(strip=True) if title_tag else "",
                company=company_tag.get_text(strip=True) if company_tag else "",
                location=location_tag.get_text(strip=True) if location_tag else "",
                description=description,
                url=job_url,
            )
        except Exception as e:
            logger.error(f"Error getting job details: {e}")
            return None

    def _parse_job_cards(self, html: str) -> list[JobPosting]:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all("div", class_="base-card")
        jobs = []

        for card in cards:
            try:
                title_tag = card.find("h3", class_="base-search-card__title")
                company_tag = card.find("h4", class_="base-search-card__subtitle")
                location_tag = card.find("span", class_="job-search-card__location")
                link_tag = card.find("a", class_="base-card__full-link")
                time_tag = card.find("time")

                url = link_tag["href"].split("?")[0] if link_tag else ""
                external_id = url.split("-")[-1] if url else hashlib.md5(
                    (title_tag.get_text(strip=True) if title_tag else "").encode()
                ).hexdigest()[:12]

                job = JobPosting(
                    external_id=str(external_id),
                    platform="linkedin",
                    title=title_tag.get_text(strip=True) if title_tag else "",
                    company=company_tag.get_text(strip=True) if company_tag else "",
                    location=location_tag.get_text(strip=True) if location_tag else "",
                    url=url,
                    is_easy_apply="Easy Apply" in card.get_text(),
                )
                if job.title:
                    jobs.append(job)
            except Exception as e:
                logger.debug(f"Error parsing job card: {e}")
                continue

        return jobs

    @staticmethod
    def _time_filter(hours: int) -> str:
        if hours <= 24:
            return "r86400"
        elif hours <= 168:
            return "r604800"
        elif hours <= 720:
            return "r2592000"
        return ""

    @staticmethod
    def _job_type_code(job_type: str) -> str:
        mapping = {
            "full-time": "F",
            "part-time": "P",
            "contract": "C",
            "internship": "I",
            "temporary": "T",
        }
        return mapping.get(job_type.lower(), "")
