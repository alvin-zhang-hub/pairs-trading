# scrapers/indeed.py
import random
import time

import requests
from bs4 import BeautifulSoup

from config import REQUEST_DELAY_MIN, REQUEST_DELAY_MAX
from models import Job
from scrapers.base import BaseScraper

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
]

BASE_URL = "https://www.indeed.com/jobs"


class IndeedScraper(BaseScraper):
    def scrape(self, search_terms: list[str], locations: list[str]) -> list[Job]:
        seen_urls: set[str] = set()
        jobs: list[Job] = []

        for title in search_terms:
            for location in locations:
                try:
                    page_jobs = self._scrape_query(title, location)
                    for job in page_jobs:
                        if job.url not in seen_urls:
                            seen_urls.add(job.url)
                            jobs.append(job)
                except Exception:
                    continue
                time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

        return jobs

    def _scrape_query(self, title: str, location: str) -> list[Job]:
        params = {
            "q": title,
            "l": location,
            "fromage": 1,
            "sort": "date",
        }
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = requests.get(BASE_URL, params=params, headers=headers, timeout=15)

        if resp.status_code != 200:
            return []

        return self._parse_jobs(resp.text)

    def _parse_jobs(self, html: str) -> list[Job]:
        soup = BeautifulSoup(html, "lxml")
        cards = soup.find_all("div", class_="job_seen_beacon")
        jobs: list[Job] = []

        for card in cards:
            try:
                title_tag = card.find("h2", class_="jobTitle")
                title_span = title_tag.find("span") if title_tag else None
                title = title_span.get_text(strip=True) if title_span else ""

                link_tag = title_tag.find("a") if title_tag else None
                href = link_tag.get("href", "") if link_tag else ""
                url = f"https://www.indeed.com{href}" if href and not href.startswith("http") else href

                company_tag = card.find("span", attrs={"data-testid": "company-name"})
                company = company_tag.get_text(strip=True) if company_tag else ""

                location_tag = card.find("div", attrs={"data-testid": "text-location"})
                location = location_tag.get_text(strip=True) if location_tag else ""

                date_tag = card.find("span", class_="date")
                posted_date = date_tag.get_text(strip=True) if date_tag else None

                if url and title:
                    jobs.append(
                        Job(
                            title=title,
                            company=company,
                            location=location,
                            url=url,
                            source="indeed",
                            posted_date=posted_date,
                            salary=None,
                            description="",
                        )
                    )
            except Exception:
                continue

        return jobs
