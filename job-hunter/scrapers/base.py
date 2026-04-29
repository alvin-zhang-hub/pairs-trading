# scrapers/base.py
from abc import ABC, abstractmethod

from models import Job


class BaseScraper(ABC):
    @abstractmethod
    def scrape(self, search_terms: list[str], locations: list[str]) -> list[Job]:
        """Scrape job listings for the given search terms and locations.

        Returns a list of Job objects. Must not raise on transient failures —
        return an empty list and log the error instead.
        """
        ...
