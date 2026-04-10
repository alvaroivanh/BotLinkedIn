from abc import ABC, abstractmethod

from src.scraper.models import JobPosting, SearchCriteria, SearchResult


class BaseScraper(ABC):
    @abstractmethod
    def search(self, criteria: SearchCriteria) -> SearchResult:
        """Search for job postings matching the given criteria."""
        ...

    @abstractmethod
    def get_details(self, job_url: str) -> JobPosting | None:
        """Get detailed information for a specific job posting."""
        ...
