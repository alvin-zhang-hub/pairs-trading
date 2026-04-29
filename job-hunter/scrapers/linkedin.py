# scrapers/linkedin.py
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

BASE_URL = "https://www.linkedin.com/jobs/search/"


class LinkedInScraper(BaseScraper):
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
            "keywords": title,
            "location": location,
            "f_TPR": "r86400",
            "position": 1,
            "pageNum": 0,
        }
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = requests.get(BASE_URL, params=params, headers=headers, timeout=15)

        if resp.status_code != 200:
            return []

        return self._parse_jobs(resp.text)

    def _parse_jobs(self, html: str) -> list[Job]:
        soup = BeautifulSoup(html, "lxml")
        cards = soup.find_all("div", class_="base-card")
        jobs: list[Job] = []

        for card in cards:
            try:
                link_tag = card.find("a", class_="base-card__full-link")
                url = link_tag["href"].strip() if link_tag else ""

                title_tag = card.find("h3", class_="base-search-card__title")
                title = title_tag.get_text(strip=True) if title_tag else ""

                company_tag = card.find("h4", class_="base-search-card__subtitle")
                company = company_tag.get_text(strip=True) if company_tag else ""

                location_tag = card.find("span", class_="job-search-card__location")
                location = location_tag.get_text(strip=True) if location_tag else ""

                date_tag = card.find("time", class_="job-search-card__listdate")
                posted_date = date_tag.get("datetime") if date_tag else None

                if url and title:
                    jobs.append(
                        Job(
                            title=title,
                            company=company,
                            location=location,
                            url=url,
                            source="linkedin",
                            posted_date=posted_date,
                            salary=None,
                            description="",
                        )
                    )
            except Exception:
                continue

        return jobs
