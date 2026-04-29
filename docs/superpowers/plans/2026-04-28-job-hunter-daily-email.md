# Job Hunter Daily Email — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automated daily pipeline that scrapes LinkedIn and Indeed for job listings, deduplicates, scores against Alvin's profile, and emails the top 20 matches at 5pm ET via GitHub Actions.

**Architecture:** Modular pipeline with separate scraper, scoring, persistence, and email modules behind clean interfaces. An orchestrator ties them together. SQLite database persisted via git commit tracks seen jobs for deduplication.

**Tech Stack:** Python 3.13, requests, BeautifulSoup4, lxml, sqlite3, smtplib, GitHub Actions

---

## File Structure

```
job-hunter/
  models.py              # Job dataclass — shared contract between all modules
  config.py              # Search parameters (titles, locations) and email settings
  scrapers/
    __init__.py
    base.py              # BaseScraper ABC — defines scrape() interface
    linkedin.py          # LinkedInScraper — public job search page parser
    indeed.py            # IndeedScraper — indeed.com search page parser
  scoring/
    __init__.py
    profile.py           # Target titles, skills, hard-filter terms, scoring weights
    scorer.py            # score_job() and filter_and_rank() — two-phase scoring
  store/
    __init__.py
    job_store.py         # JobStore class — SQLite wrapper for dedup and persistence
  email/
    __init__.py
    template.py          # render_email() — builds HTML email body from scored jobs
    sender.py            # send_email() — Gmail SMTP transport
  orchestrator.py        # main() — scrape → dedup → score → email → persist
  requirements.txt       # requests, beautifulsoup4, lxml
  data/                  # SQLite database lives here (committed to git)
  tests/
    __init__.py
    test_models.py
    test_job_store.py
    test_scorer.py
    test_profile.py
    test_template.py
    test_sender.py
    test_linkedin.py
    test_indeed.py
    test_orchestrator.py
  .github/
    workflows/
      daily-jobs.yml     # Cron schedule + auto-commit of jobs.db
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `job-hunter/models.py`
- Create: `job-hunter/config.py`
- Create: `job-hunter/requirements.txt`
- Create: `job-hunter/tests/__init__.py`
- Create: `job-hunter/tests/test_models.py`
- Create: `job-hunter/scrapers/__init__.py`
- Create: `job-hunter/scoring/__init__.py`
- Create: `job-hunter/store/__init__.py`
- Create: `job-hunter/email/__init__.py`
- Create: `job-hunter/data/.gitkeep`

- [ ] **Step 1: Create the project directory and all `__init__.py` files**

```bash
mkdir -p job-hunter/{scrapers,scoring,store,email,tests,data}
touch job-hunter/scrapers/__init__.py
touch job-hunter/scoring/__init__.py
touch job-hunter/store/__init__.py
touch job-hunter/email/__init__.py
touch job-hunter/tests/__init__.py
touch job-hunter/data/.gitkeep
```

- [ ] **Step 2: Create `requirements.txt`**

```
# job-hunter/requirements.txt
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
pytest>=8.0.0
```

- [ ] **Step 3: Create `models.py` with the Job dataclass**

```python
# job-hunter/models.py
from dataclasses import dataclass


@dataclass
class Job:
    title: str
    company: str
    location: str
    url: str
    source: str
    posted_date: str | None
    salary: str | None
    description: str
```

- [ ] **Step 4: Create `config.py` with search parameters and email settings**

```python
# job-hunter/config.py
import os

SEARCH_TITLES = [
    "Product Analyst",
    "Senior Product Analyst",
    "Analytics Lead",
    "Analytics Manager",
    "Head of Analytics",
    "Analytics Engineer",
    "Growth Analyst",
    "Product Manager",
    "Strategy & Operations",
    "Chief of Staff",
    "RevOps",
]

SEARCH_LOCATIONS = [
    "Remote",
    "Boston",
    "Seattle",
    "New York",
    "Los Angeles",
    "San Diego",
    "San Francisco",
]

EMAIL_RECIPIENT = os.environ.get("GMAIL_ADDRESS", "azhang2100@gmail.com")
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "azhang2100@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

TOP_N = 20
MIN_SCORE = 30

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "jobs.db")

REQUEST_DELAY_MIN = 2
REQUEST_DELAY_MAX = 5
```

- [ ] **Step 5: Write the test for the Job dataclass**

```python
# job-hunter/tests/test_models.py
from models import Job


def test_job_creation():
    job = Job(
        title="Senior Product Analyst",
        company="Stripe",
        location="Remote",
        url="https://example.com/job/123",
        source="linkedin",
        posted_date="2026-04-28",
        salary="$130k-$160k",
        description="We are looking for a Senior Product Analyst...",
    )
    assert job.title == "Senior Product Analyst"
    assert job.source == "linkedin"
    assert job.salary == "$130k-$160k"


def test_job_creation_nullable_fields():
    job = Job(
        title="Analytics Lead",
        company="Acme",
        location="Boston",
        url="https://example.com/job/456",
        source="indeed",
        posted_date=None,
        salary=None,
        description="Looking for an analytics lead...",
    )
    assert job.posted_date is None
    assert job.salary is None
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd job-hunter && python -m pytest tests/test_models.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add job-hunter/
git commit -m "feat: project scaffolding — models, config, requirements"
```

---

### Task 2: Profile Configuration

**Files:**
- Create: `job-hunter/scoring/profile.py`
- Create: `job-hunter/tests/test_profile.py`

- [ ] **Step 1: Write the test for profile configuration**

```python
# job-hunter/tests/test_profile.py
from scoring.profile import (
    TARGET_TITLES,
    TITLE_KEYWORDS,
    RELATED_TITLES,
    PROFILE_SKILLS,
    SENIORITY_TERMS,
    HARD_FILTER_TITLES,
    HARD_FILTER_DESCRIPTION,
    INDUSTRY_TIERS,
)


def test_target_titles_exist():
    assert "Product Analyst" in TARGET_TITLES
    assert "Analytics Lead" in TARGET_TITLES
    assert len(TARGET_TITLES) == 11


def test_hard_filter_titles_exclude_engineering():
    assert "software engineer" in HARD_FILTER_TITLES
    assert "machine learning engineer" in HARD_FILTER_TITLES
    assert "sde" in HARD_FILTER_TITLES


def test_profile_skills_include_core():
    assert "sql" in PROFILE_SKILLS
    assert "python" in PROFILE_SKILLS
    assert "a/b testing" in PROFILE_SKILLS


def test_industry_tiers_ordered():
    assert INDUSTRY_TIERS["fintech"] > INDUSTRY_TIERS["e-commerce"]
    assert INDUSTRY_TIERS["e-commerce"] > INDUSTRY_TIERS["tech"]
    assert INDUSTRY_TIERS["tech"] > INDUSTRY_TIERS["other"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd job-hunter && python -m pytest tests/test_profile.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'scoring.profile'`

- [ ] **Step 3: Implement `profile.py`**

```python
# job-hunter/scoring/profile.py

# Exact target titles — score 35 for exact match (case-insensitive)
TARGET_TITLES = [
    "product analyst",
    "senior product analyst",
    "analytics lead",
    "analytics manager",
    "head of analytics",
    "analytics engineer",
    "growth analyst",
    "product manager",
    "strategy & operations",
    "chief of staff",
    "revops",
]

# Keywords that earn 25 if found in title — partial match
TITLE_KEYWORDS = [
    "analytics",
    "product analyst",
    "product manager",
    "growth",
    "strategy",
    "operations",
    "revops",
]

# Related titles that earn 15 — weaker match
RELATED_TITLES = [
    "data analyst",
    "business analyst",
    "business intelligence",
    "insights analyst",
    "decision scientist",
]

# Skills to look for in descriptions — each match adds points toward 25 max
PROFILE_SKILLS = [
    "sql",
    "python",
    "dbt",
    "a/b testing",
    "experimentation",
    "causal inference",
    "funnel analysis",
    "data modeling",
    "databricks",
    "looker",
    "tableau",
    "power bi",
    "cohort analysis",
]

# Seniority terms in title — "Senior"/"Lead"/"Manager" = 15, "Staff" = 10
SENIORITY_TERMS = {
    "senior": 15,
    "lead": 15,
    "manager": 15,
    "head": 15,
    "director": 15,
    "staff": 10,
}
SENIORITY_DEFAULT = 5  # no seniority indicator in title

# Hard filter — reject if title contains any of these (case-insensitive)
HARD_FILTER_TITLES = [
    "machine learning engineer",
    "software engineer",
    "sde",
    "data engineer",
    "intern",
    "junior",
    "entry level",
]

# Hard filter — reject if description contains any of these (case-insensitive)
HARD_FILTER_DESCRIPTION = [
    "phd required",
    "5+ years ml/ai experience",
    "deep learning frameworks",
    "system design interviews",
]

# Industry keyword tiers — points awarded based on best match
INDUSTRY_TIERS = {
    "fintech": 10,
    "financial services": 10,
    "payments": 10,
    "banking": 10,
    "neobank": 10,
    "e-commerce": 7,
    "ecommerce": 7,
    "retail": 7,
    "marketplace": 7,
    "tech": 5,
    "saas": 5,
    "software": 5,
    "other": 2,
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd job-hunter && python -m pytest tests/test_profile.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add job-hunter/scoring/profile.py job-hunter/tests/test_profile.py
git commit -m "feat: profile config — target titles, skills, filters, scoring weights"
```

---

### Task 3: Job Store (SQLite Persistence)

**Files:**
- Create: `job-hunter/store/job_store.py`
- Create: `job-hunter/tests/test_job_store.py`

- [ ] **Step 1: Write the failing tests**

```python
# job-hunter/tests/test_job_store.py
import os
import tempfile

from models import Job
from store.job_store import JobStore


def _make_job(url="https://example.com/job/1", title="Analyst"):
    return Job(
        title=title,
        company="Acme",
        location="Remote",
        url=url,
        source="linkedin",
        posted_date="2026-04-28",
        salary=None,
        description="A job description.",
    )


def test_is_seen_returns_false_for_new_job():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        store = JobStore(db_path)
        assert store.is_seen("https://example.com/job/1") is False


def test_mark_seen_then_is_seen():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        store = JobStore(db_path)
        job = _make_job()
        store.mark_seen(job, score=85, emailed=True)
        assert store.is_seen(job.url) is True


def test_filter_new_jobs():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        store = JobStore(db_path)
        job1 = _make_job(url="https://example.com/1")
        job2 = _make_job(url="https://example.com/2")
        store.mark_seen(job1, score=50, emailed=True)
        new_jobs = store.filter_new([job1, job2])
        assert len(new_jobs) == 1
        assert new_jobs[0].url == "https://example.com/2"


def test_mark_seen_batch():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        store = JobStore(db_path)
        jobs = [_make_job(url=f"https://example.com/{i}") for i in range(5)]
        scores = {j.url: 50 + i for i, j in enumerate(jobs)}
        store.mark_seen_batch(jobs, scores)
        assert store.is_seen("https://example.com/0") is True
        assert store.is_seen("https://example.com/4") is True
        assert store.is_seen("https://example.com/99") is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd job-hunter && python -m pytest tests/test_job_store.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'store.job_store'`

- [ ] **Step 3: Implement `job_store.py`**

```python
# job-hunter/store/job_store.py
import sqlite3
from datetime import date

from models import Job


class JobStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._create_table()

    def _create_table(self):
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs_seen (
                url TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                source TEXT,
                first_seen DATE,
                score INTEGER,
                emailed BOOLEAN
            )
            """
        )
        self._conn.commit()

    def is_seen(self, url: str) -> bool:
        cursor = self._conn.execute(
            "SELECT 1 FROM jobs_seen WHERE url = ?", (url,)
        )
        return cursor.fetchone() is not None

    def filter_new(self, jobs: list[Job]) -> list[Job]:
        return [job for job in jobs if not self.is_seen(job.url)]

    def mark_seen(self, job: Job, score: int, emailed: bool):
        self._conn.execute(
            """
            INSERT OR IGNORE INTO jobs_seen (url, title, company, source, first_seen, score, emailed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (job.url, job.title, job.company, job.source, date.today().isoformat(), score, emailed),
        )
        self._conn.commit()

    def mark_seen_batch(self, jobs: list[Job], scores: dict[str, int]):
        today = date.today().isoformat()
        rows = [
            (job.url, job.title, job.company, job.source, today, scores.get(job.url, 0), True)
            for job in jobs
        ]
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO jobs_seen (url, title, company, source, first_seen, score, emailed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._conn.commit()

    def close(self):
        self._conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd job-hunter && python -m pytest tests/test_job_store.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add job-hunter/store/job_store.py job-hunter/tests/test_job_store.py
git commit -m "feat: job store — SQLite persistence for dedup and seen tracking"
```

---

### Task 4: Scraper Base Class

**Files:**
- Create: `job-hunter/scrapers/base.py`

- [ ] **Step 1: Create the abstract base scraper**

```python
# job-hunter/scrapers/base.py
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
```

- [ ] **Step 2: Commit**

```bash
git add job-hunter/scrapers/base.py
git commit -m "feat: base scraper ABC — defines scrape() interface"
```

---

### Task 5: LinkedIn Scraper

**Files:**
- Create: `job-hunter/scrapers/linkedin.py`
- Create: `job-hunter/tests/test_linkedin.py`

- [ ] **Step 1: Write the failing tests**

Tests use a saved HTML fixture to avoid hitting LinkedIn in tests.

```python
# job-hunter/tests/test_linkedin.py
from unittest.mock import patch, MagicMock

from scrapers.linkedin import LinkedInScraper

SAMPLE_HTML = """
<html>
<body>
<div class="base-card" data-entity-urn="urn:li:jobPosting:12345">
  <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/12345">
  </a>
  <h3 class="base-search-card__title">Senior Product Analyst</h3>
  <h4 class="base-search-card__subtitle">
    <a>Stripe</a>
  </h4>
  <span class="job-search-card__location">Remote</span>
  <time class="job-search-card__listdate" datetime="2026-04-27"></time>
</div>
<div class="base-card" data-entity-urn="urn:li:jobPosting:67890">
  <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/67890">
  </a>
  <h3 class="base-search-card__title">Analytics Manager</h3>
  <h4 class="base-search-card__subtitle">
    <a>Robinhood</a>
  </h4>
  <span class="job-search-card__location">New York, NY</span>
  <time class="job-search-card__listdate" datetime="2026-04-26"></time>
</div>
</body>
</html>
"""


def _mock_response(html, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = html
    return resp


@patch("scrapers.linkedin.requests.get")
@patch("scrapers.linkedin.time.sleep")
def test_scrape_parses_linkedin_html(mock_sleep, mock_get):
    mock_get.return_value = _mock_response(SAMPLE_HTML)
    scraper = LinkedInScraper()
    jobs = scraper.scrape(["Product Analyst"], ["Remote"])
    assert len(jobs) >= 2
    assert jobs[0].title == "Senior Product Analyst"
    assert jobs[0].company == "Stripe"
    assert jobs[0].source == "linkedin"
    assert "linkedin.com/jobs/view/12345" in jobs[0].url


@patch("scrapers.linkedin.requests.get")
@patch("scrapers.linkedin.time.sleep")
def test_scrape_returns_empty_on_failure(mock_sleep, mock_get):
    mock_get.side_effect = Exception("Connection refused")
    scraper = LinkedInScraper()
    jobs = scraper.scrape(["Product Analyst"], ["Remote"])
    assert jobs == []


@patch("scrapers.linkedin.requests.get")
@patch("scrapers.linkedin.time.sleep")
def test_scrape_deduplicates_across_queries(mock_sleep, mock_get):
    mock_get.return_value = _mock_response(SAMPLE_HTML)
    scraper = LinkedInScraper()
    # Two queries that return the same HTML — should dedup by URL
    jobs = scraper.scrape(["Product Analyst", "Analytics Manager"], ["Remote"])
    urls = [j.url for j in jobs]
    assert len(urls) == len(set(urls))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd job-hunter && python -m pytest tests/test_linkedin.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'scrapers.linkedin'`

- [ ] **Step 3: Implement LinkedIn scraper**

```python
# job-hunter/scrapers/linkedin.py
import random
import time
from urllib.parse import quote_plus

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
            "f_TPR": "r86400",  # past 24 hours
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd job-hunter && python -m pytest tests/test_linkedin.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add job-hunter/scrapers/linkedin.py job-hunter/tests/test_linkedin.py
git commit -m "feat: LinkedIn scraper — parses public job search pages"
```

---

### Task 6: Indeed Scraper

**Files:**
- Create: `job-hunter/scrapers/indeed.py`
- Create: `job-hunter/tests/test_indeed.py`

- [ ] **Step 1: Write the failing tests**

```python
# job-hunter/tests/test_indeed.py
from unittest.mock import patch, MagicMock

from scrapers.indeed import IndeedScraper

SAMPLE_HTML = """
<html>
<body>
<div id="mosaic-provider-jobcards">
  <ul>
    <li>
      <div class="job_seen_beacon" data-jk="abc123">
        <h2 class="jobTitle">
          <a href="/viewjob?jk=abc123">
            <span>Product Analytics Lead</span>
          </a>
        </h2>
        <span data-testid="company-name">Cash App</span>
        <div data-testid="text-location">San Francisco, CA</div>
        <span class="date">Posted 1 day ago</span>
      </div>
    </li>
    <li>
      <div class="job_seen_beacon" data-jk="def456">
        <h2 class="jobTitle">
          <a href="/viewjob?jk=def456">
            <span>Senior Growth Analyst</span>
          </a>
        </h2>
        <span data-testid="company-name">Duolingo</span>
        <div data-testid="text-location">Remote</div>
        <span class="date">Posted today</span>
      </div>
    </li>
  </ul>
</div>
</body>
</html>
"""


def _mock_response(html, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = html
    return resp


@patch("scrapers.indeed.requests.get")
@patch("scrapers.indeed.time.sleep")
def test_scrape_parses_indeed_html(mock_sleep, mock_get):
    mock_get.return_value = _mock_response(SAMPLE_HTML)
    scraper = IndeedScraper()
    jobs = scraper.scrape(["Product Analyst"], ["San Francisco"])
    assert len(jobs) >= 2
    assert jobs[0].title == "Product Analytics Lead"
    assert jobs[0].company == "Cash App"
    assert jobs[0].source == "indeed"
    assert "indeed.com" in jobs[0].url


@patch("scrapers.indeed.requests.get")
@patch("scrapers.indeed.time.sleep")
def test_scrape_returns_empty_on_failure(mock_sleep, mock_get):
    mock_get.side_effect = Exception("Timeout")
    scraper = IndeedScraper()
    jobs = scraper.scrape(["Product Analyst"], ["Remote"])
    assert jobs == []


@patch("scrapers.indeed.requests.get")
@patch("scrapers.indeed.time.sleep")
def test_scrape_deduplicates_across_queries(mock_sleep, mock_get):
    mock_get.return_value = _mock_response(SAMPLE_HTML)
    scraper = IndeedScraper()
    jobs = scraper.scrape(["Product Analyst", "Growth Analyst"], ["Remote"])
    urls = [j.url for j in jobs]
    assert len(urls) == len(set(urls))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd job-hunter && python -m pytest tests/test_indeed.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'scrapers.indeed'`

- [ ] **Step 3: Implement Indeed scraper**

```python
# job-hunter/scrapers/indeed.py
import random
import time
from urllib.parse import quote_plus

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
            "fromage": 1,  # past 24 hours
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd job-hunter && python -m pytest tests/test_indeed.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add job-hunter/scrapers/indeed.py job-hunter/tests/test_indeed.py
git commit -m "feat: Indeed scraper — parses indeed.com job search pages"
```

---

### Task 7: Scoring Engine

**Files:**
- Create: `job-hunter/scoring/scorer.py`
- Create: `job-hunter/tests/test_scorer.py`

- [ ] **Step 1: Write the failing tests**

```python
# job-hunter/tests/test_scorer.py
from models import Job
from scoring.scorer import score_job, filter_and_rank


def _make_job(
    title="Senior Product Analyst",
    company="Stripe",
    location="Remote",
    description="We need someone with SQL, Python, A/B testing, and experimentation skills. Fintech company.",
):
    return Job(
        title=title,
        company=company,
        location=location,
        url=f"https://example.com/{title.replace(' ', '-').lower()}",
        source="linkedin",
        posted_date="2026-04-28",
        salary=None,
        description=description,
    )


def test_score_exact_title_match():
    job = _make_job(title="Senior Product Analyst")
    score = score_job(job)
    assert score >= 35  # exact title match alone is 35


def test_score_keyword_title_match():
    job = _make_job(title="Business Analytics Lead")
    score = score_job(job)
    assert score >= 25  # keyword "analytics" match


def test_score_related_title_match():
    job = _make_job(title="Data Analyst")
    score = score_job(job)
    assert score >= 15  # related title match


def test_score_no_title_match():
    job = _make_job(title="Nurse Practitioner", description="Healthcare role.")
    score = score_job(job)
    assert score < 30  # should be below minimum threshold


def test_hard_filter_rejects_swe():
    job = _make_job(title="Software Engineer")
    score = score_job(job)
    assert score == -1  # sentinel for hard-filtered


def test_hard_filter_rejects_ml_engineer():
    job = _make_job(title="Machine Learning Engineer")
    score = score_job(job)
    assert score == -1


def test_hard_filter_rejects_intern():
    job = _make_job(title="Product Analyst Intern")
    score = score_job(job)
    assert score == -1


def test_hard_filter_rejects_phd_required():
    job = _make_job(
        title="Senior Product Analyst",
        description="PhD required. Deep learning frameworks experience needed.",
    )
    score = score_job(job)
    assert score == -1


def test_skills_boost_score():
    job_with_skills = _make_job(description="SQL, Python, DBT, A/B testing, experimentation, Looker")
    job_no_skills = _make_job(description="No relevant skills listed here.")
    assert score_job(job_with_skills) > score_job(job_no_skills)


def test_seniority_boost():
    senior = _make_job(title="Senior Product Analyst")
    no_seniority = _make_job(title="Product Analyst")
    assert score_job(senior) > score_job(no_seniority)


def test_location_scoring_remote():
    remote = _make_job(location="Remote")
    score = score_job(remote)
    # Remote should get full 15 location points
    assert score >= 15


def test_industry_bonus_fintech():
    fintech = _make_job(description="SQL, Python. Fintech company building payments products.")
    generic = _make_job(description="SQL, Python. We make widgets.")
    assert score_job(fintech) > score_job(generic)


def test_filter_and_rank_top_n():
    jobs = [
        _make_job(title="Senior Product Analyst", description="SQL, Python, A/B testing. Fintech."),
        _make_job(title="Software Engineer", description="Java, microservices."),
        _make_job(title="Nurse Practitioner", description="Healthcare role."),
        _make_job(title="Analytics Manager", description="SQL, experimentation, Looker. E-commerce."),
    ]
    ranked = filter_and_rank(jobs, top_n=2, min_score=30)
    # SWE should be hard-filtered, Nurse should be below threshold
    assert len(ranked) <= 2
    assert all(score >= 30 for _, score in ranked)
    # No software engineer in results
    assert all("Software Engineer" not in job.title for job, _ in ranked)


def test_filter_and_rank_respects_min_score():
    jobs = [_make_job(title="Nurse Practitioner", description="Healthcare.")]
    ranked = filter_and_rank(jobs, top_n=20, min_score=30)
    assert len(ranked) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd job-hunter && python -m pytest tests/test_scorer.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'scoring.scorer'`

- [ ] **Step 3: Implement `scorer.py`**

```python
# job-hunter/scoring/scorer.py
from models import Job
from scoring.profile import (
    TARGET_TITLES,
    TITLE_KEYWORDS,
    RELATED_TITLES,
    PROFILE_SKILLS,
    SENIORITY_TERMS,
    SENIORITY_DEFAULT,
    HARD_FILTER_TITLES,
    HARD_FILTER_DESCRIPTION,
    INDUSTRY_TIERS,
)


def score_job(job: Job) -> int:
    """Score a job from 0-100, or return -1 if hard-filtered."""
    title_lower = job.title.lower()
    desc_lower = job.description.lower()

    # --- Hard filters ---
    for term in HARD_FILTER_TITLES:
        if term in title_lower:
            return -1

    for term in HARD_FILTER_DESCRIPTION:
        if term in desc_lower:
            return -1

    score = 0

    # --- Title match (max 35) ---
    if title_lower in TARGET_TITLES:
        score += 35
    elif any(kw in title_lower for kw in TITLE_KEYWORDS):
        score += 25
    elif any(rt in title_lower for rt in RELATED_TITLES):
        score += 15

    # --- Skills overlap (max 25) ---
    matched_skills = sum(1 for skill in PROFILE_SKILLS if skill in desc_lower)
    skills_score = min(25, round(matched_skills / len(PROFILE_SKILLS) * 25))
    score += skills_score

    # --- Seniority fit (max 15) ---
    seniority_score = SENIORITY_DEFAULT
    for term, points in SENIORITY_TERMS.items():
        if term in title_lower:
            seniority_score = points
            break
    score += seniority_score

    # --- Location match (max 15) ---
    location_lower = job.location.lower()
    target_locations = ["remote", "boston", "seattle", "new york", "los angeles", "san diego", "san francisco"]
    if "remote" in location_lower:
        score += 15
    elif any(city in location_lower for city in target_locations):
        score += 15
    elif "hybrid" in location_lower and any(city in location_lower for city in target_locations):
        score += 10

    # --- Industry bonus (max 10) ---
    best_industry = 2  # default "other"
    for keyword, points in INDUSTRY_TIERS.items():
        if keyword == "other":
            continue
        if keyword in desc_lower:
            best_industry = max(best_industry, points)
    score += best_industry

    return score


def filter_and_rank(
    jobs: list[Job], top_n: int = 20, min_score: int = 30
) -> list[tuple[Job, int]]:
    """Score all jobs, hard-filter, apply min score, return top N as (Job, score) pairs."""
    scored: list[tuple[Job, int]] = []
    for job in jobs:
        s = score_job(job)
        if s >= min_score:
            scored.append((job, s))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd job-hunter && python -m pytest tests/test_scorer.py -v
```

Expected: 14 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add job-hunter/scoring/scorer.py job-hunter/tests/test_scorer.py
git commit -m "feat: scoring engine — hard filters + 100-point soft scoring"
```

---

### Task 8: Email Template

**Files:**
- Create: `job-hunter/email/template.py`
- Create: `job-hunter/tests/test_template.py`

- [ ] **Step 1: Write the failing tests**

```python
# job-hunter/tests/test_template.py
from models import Job
from email.template import render_email


def _make_scored_jobs():
    jobs = [
        (
            Job(
                title="Senior Product Analyst",
                company="Stripe",
                location="Remote",
                url="https://linkedin.com/jobs/view/123",
                source="linkedin",
                posted_date="2026-04-28",
                salary="$130k",
                description="...",
            ),
            87,
        ),
        (
            Job(
                title="Analytics Manager",
                company="Robinhood",
                location="Boston, MA",
                url="https://indeed.com/viewjob?jk=456",
                source="indeed",
                posted_date="2026-04-27",
                salary=None,
                description="...",
            ),
            75,
        ),
    ]
    return jobs


def test_render_email_returns_subject_and_body():
    scored_jobs = _make_scored_jobs()
    stats = {"total_scraped": 200, "new_today": 30, "passed_filters": 15}
    source_status = {"linkedin": True, "indeed": True}
    subject, body = render_email(scored_jobs, stats, source_status)
    assert "Job Hunter Daily" in subject
    assert "2 new listings" in subject


def test_render_email_contains_job_details():
    scored_jobs = _make_scored_jobs()
    stats = {"total_scraped": 200, "new_today": 30, "passed_filters": 15}
    source_status = {"linkedin": True, "indeed": True}
    _, body = render_email(scored_jobs, stats, source_status)
    assert "Senior Product Analyst" in body
    assert "Stripe" in body
    assert "Remote" in body
    assert "87" in body
    assert "linkedin.com/jobs/view/123" in body


def test_render_email_contains_footer_stats():
    scored_jobs = _make_scored_jobs()
    stats = {"total_scraped": 200, "new_today": 30, "passed_filters": 15}
    source_status = {"linkedin": True, "indeed": False}
    _, body = render_email(scored_jobs, stats, source_status)
    assert "200" in body
    assert "30" in body


def test_render_email_empty_jobs():
    stats = {"total_scraped": 50, "new_today": 0, "passed_filters": 0}
    source_status = {"linkedin": True, "indeed": True}
    subject, body = render_email([], stats, source_status)
    assert "0 new listings" in subject
    assert "No matching jobs" in body
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd job-hunter && python -m pytest tests/test_template.py -v
```

Expected: FAIL — `ImportError: cannot import name 'render_email' from 'email.template'`

Note: Python has a built-in `email` module. Our `email/` package will shadow it locally. The tests import `from email.template import render_email` — this works because Python resolves local packages first. The sender module will need to import `smtplib` directly (which is separate from the `email` package name collision). **If this causes issues, we rename our package to `mailer/` in a quick fix.**

- [ ] **Step 3: Implement `template.py`**

```python
# job-hunter/email/template.py
from datetime import date

from models import Job


def render_email(
    scored_jobs: list[tuple[Job, int]],
    stats: dict,
    source_status: dict[str, bool],
) -> tuple[str, str]:
    """Render the daily email. Returns (subject, html_body)."""
    today = date.today().strftime("%B %d, %Y")
    count = len(scored_jobs)
    subject = f"Job Hunter Daily \u2014 {today} ({count} new listings)"

    if not scored_jobs:
        body = _render_empty(stats, source_status, today)
    else:
        body = _render_full(scored_jobs, stats, source_status, today)

    return subject, body


def _render_full(
    scored_jobs: list[tuple[Job, int]],
    stats: dict,
    source_status: dict[str, bool],
    today: str,
) -> str:
    rows = ""
    for i, (job, score) in enumerate(scored_jobs, 1):
        salary_cell = job.salary if job.salary else "\u2014"
        rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #eee;">{i}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;"><strong>{score}</strong></td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{job.title}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{job.company}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{job.location}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{salary_cell}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">
                <a href="{job.url}" style="color:#2563eb;">Apply &rarr;</a>
            </td>
        </tr>"""

    sources = " | ".join(
        f"{name} {'&#10003;' if ok else '&#10007;'}"
        for name, ok in source_status.items()
    )

    return f"""
    <html>
    <body style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:20px;">
        <h2>Job Hunter Daily &mdash; {today}</h2>
        <p>Hey Alvin,</p>
        <p>Here are today's top matches, ranked by fit:</p>
        <table style="border-collapse:collapse;width:100%;font-size:14px;">
            <thead>
                <tr style="background:#f8f9fa;">
                    <th style="padding:8px;text-align:left;">#</th>
                    <th style="padding:8px;text-align:left;">Score</th>
                    <th style="padding:8px;text-align:left;">Title</th>
                    <th style="padding:8px;text-align:left;">Company</th>
                    <th style="padding:8px;text-align:left;">Location</th>
                    <th style="padding:8px;text-align:left;">Salary</th>
                    <th style="padding:8px;text-align:left;">Link</th>
                </tr>
            </thead>
            <tbody>{rows}
            </tbody>
        </table>
        <hr style="margin:20px 0;border:none;border-top:1px solid #ddd;">
        <p style="font-size:12px;color:#666;">
            Sources checked: {sources}<br>
            Total scraped: {stats['total_scraped']} | New today: {stats['new_today']} | Passed filters: {stats['passed_filters']}
        </p>
    </body>
    </html>
    """


def _render_empty(stats: dict, source_status: dict[str, bool], today: str) -> str:
    sources = " | ".join(
        f"{name} {'&#10003;' if ok else '&#10007;'}"
        for name, ok in source_status.items()
    )
    return f"""
    <html>
    <body style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:20px;">
        <h2>Job Hunter Daily &mdash; {today}</h2>
        <p>Hey Alvin,</p>
        <p>No matching jobs found today. This could mean all today's listings were already seen, or scrapers hit rate limits.</p>
        <hr style="margin:20px 0;border:none;border-top:1px solid #ddd;">
        <p style="font-size:12px;color:#666;">
            Sources checked: {sources}<br>
            Total scraped: {stats['total_scraped']} | New today: {stats['new_today']} | Passed filters: {stats['passed_filters']}
        </p>
    </body>
    </html>
    """
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd job-hunter && python -m pytest tests/test_template.py -v
```

Expected: 4 tests PASS. If the `email` package name collision causes issues, rename `email/` to `mailer/` and update imports.

- [ ] **Step 5: Commit**

```bash
git add job-hunter/email/template.py job-hunter/tests/test_template.py
git commit -m "feat: email template — HTML rendering for daily job digest"
```

---

### Task 9: Email Sender

**Files:**
- Create: `job-hunter/email/sender.py`
- Create: `job-hunter/tests/test_sender.py`

- [ ] **Step 1: Write the failing tests**

```python
# job-hunter/tests/test_sender.py
from unittest.mock import patch, MagicMock

from email.sender import send_email


@patch("email.sender.smtplib.SMTP_SSL")
def test_send_email_calls_smtp(mock_smtp_class):
    mock_server = MagicMock()
    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

    send_email(
        subject="Test Subject",
        html_body="<p>Hello</p>",
        to_addr="test@example.com",
        from_addr="sender@example.com",
        app_password="fake-password",
    )

    mock_smtp_class.assert_called_once_with("smtp.gmail.com", 465)
    mock_server.login.assert_called_once_with("sender@example.com", "fake-password")
    mock_server.send_message.assert_called_once()


@patch("email.sender.smtplib.SMTP_SSL")
def test_send_email_message_has_correct_subject(mock_smtp_class):
    mock_server = MagicMock()
    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

    send_email(
        subject="Job Hunter Daily",
        html_body="<p>Jobs</p>",
        to_addr="test@example.com",
        from_addr="sender@example.com",
        app_password="fake-password",
    )

    sent_msg = mock_server.send_message.call_args[0][0]
    assert sent_msg["Subject"] == "Job Hunter Daily"
    assert sent_msg["To"] == "test@example.com"
    assert sent_msg["From"] == "sender@example.com"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd job-hunter && python -m pytest tests/test_sender.py -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement `sender.py`**

```python
# job-hunter/email/sender.py
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(
    subject: str,
    html_body: str,
    to_addr: str,
    from_addr: str,
    app_password: str,
):
    """Send an HTML email via Gmail SMTP SSL."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(from_addr, app_password)
        server.send_message(msg)
```

Note: This file imports from the stdlib `email.mime` — this works because `from email.mime.multipart import MIMEMultipart` resolves the stdlib, not our local `email/` package. Python handles this correctly since our package doesn't have `mime` submodule. If it causes issues, rename our package to `mailer/`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd job-hunter && python -m pytest tests/test_sender.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add job-hunter/email/sender.py job-hunter/tests/test_sender.py
git commit -m "feat: email sender — Gmail SMTP transport"
```

---

### Task 10: Orchestrator

**Files:**
- Create: `job-hunter/orchestrator.py`
- Create: `job-hunter/tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing tests**

```python
# job-hunter/tests/test_orchestrator.py
from unittest.mock import patch, MagicMock
import tempfile
import os

from models import Job
from orchestrator import run_pipeline


def _make_job(title="Senior Product Analyst", url="https://example.com/1"):
    return Job(
        title=title,
        company="Acme",
        location="Remote",
        url=url,
        source="linkedin",
        posted_date="2026-04-28",
        salary=None,
        description="SQL, Python, A/B testing, experimentation. Fintech company.",
    )


@patch("orchestrator.send_email")
@patch("orchestrator.IndeedScraper")
@patch("orchestrator.LinkedInScraper")
def test_pipeline_scrapes_scores_emails(mock_li_cls, mock_indeed_cls, mock_send):
    mock_li = MagicMock()
    mock_li.scrape.return_value = [_make_job(url="https://li.com/1")]
    mock_li_cls.return_value = mock_li

    mock_indeed = MagicMock()
    mock_indeed.scrape.return_value = [_make_job(url="https://indeed.com/1")]
    mock_indeed_cls.return_value = mock_indeed

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        run_pipeline(db_path=db_path)

    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args
    assert "Job Hunter Daily" in call_kwargs[1]["subject"] or "Job Hunter Daily" in call_kwargs[0][0]


@patch("orchestrator.send_email")
@patch("orchestrator.IndeedScraper")
@patch("orchestrator.LinkedInScraper")
def test_pipeline_deduplicates_across_runs(mock_li_cls, mock_indeed_cls, mock_send):
    job = _make_job(url="https://li.com/same-job")
    mock_li = MagicMock()
    mock_li.scrape.return_value = [job]
    mock_li_cls.return_value = mock_li

    mock_indeed = MagicMock()
    mock_indeed.scrape.return_value = []
    mock_indeed_cls.return_value = mock_indeed

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        # Run 1 — should email
        run_pipeline(db_path=db_path)
        assert mock_send.call_count == 1

        # Run 2 — same job, should still email but with 0 new listings
        mock_send.reset_mock()
        run_pipeline(db_path=db_path)
        assert mock_send.call_count == 1
        # The second email should have 0 scored jobs (all seen)


@patch("orchestrator.send_email")
@patch("orchestrator.IndeedScraper")
@patch("orchestrator.LinkedInScraper")
def test_pipeline_continues_if_one_scraper_fails(mock_li_cls, mock_indeed_cls, mock_send):
    mock_li = MagicMock()
    mock_li.scrape.side_effect = Exception("LinkedIn down")
    mock_li_cls.return_value = mock_li

    mock_indeed = MagicMock()
    mock_indeed.scrape.return_value = [_make_job(url="https://indeed.com/2")]
    mock_indeed_cls.return_value = mock_indeed

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        run_pipeline(db_path=db_path)

    # Should still send email with Indeed results
    mock_send.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd job-hunter && python -m pytest tests/test_orchestrator.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'orchestrator'` or import error

- [ ] **Step 3: Implement `orchestrator.py`**

```python
# job-hunter/orchestrator.py
import sys
import os

from config import (
    SEARCH_TITLES,
    SEARCH_LOCATIONS,
    GMAIL_ADDRESS,
    GMAIL_APP_PASSWORD,
    EMAIL_RECIPIENT,
    TOP_N,
    MIN_SCORE,
    DB_PATH,
)
from models import Job
from scrapers.linkedin import LinkedInScraper
from scrapers.indeed import IndeedScraper
from scoring.scorer import filter_and_rank
from store.job_store import JobStore
from email.template import render_email
from email.sender import send_email


def run_pipeline(db_path: str | None = None):
    """Main pipeline: scrape → dedup → score → email → persist."""
    if db_path is None:
        db_path = DB_PATH

    store = JobStore(db_path)
    all_jobs: list[Job] = []
    source_status: dict[str, bool] = {}

    # --- Scrape ---
    for name, scraper_cls in [("linkedin", LinkedInScraper), ("indeed", IndeedScraper)]:
        try:
            scraper = scraper_cls()
            jobs = scraper.scrape(SEARCH_TITLES, SEARCH_LOCATIONS)
            all_jobs.extend(jobs)
            source_status[name] = True
            print(f"[{name}] Scraped {len(jobs)} jobs")
        except Exception as e:
            source_status[name] = False
            print(f"[{name}] Failed: {e}")

    total_scraped = len(all_jobs)

    # --- Dedup ---
    new_jobs = store.filter_new(all_jobs)
    new_today = len(new_jobs)
    print(f"New jobs after dedup: {new_today}")

    # --- Score & rank ---
    ranked = filter_and_rank(new_jobs, top_n=TOP_N, min_score=MIN_SCORE)
    passed_filters = len(ranked)
    print(f"Jobs passing filters: {passed_filters}")

    # --- Email ---
    stats = {
        "total_scraped": total_scraped,
        "new_today": new_today,
        "passed_filters": passed_filters,
    }
    subject, html_body = render_email(ranked, stats, source_status)

    send_email(
        subject=subject,
        html_body=html_body,
        to_addr=EMAIL_RECIPIENT,
        from_addr=GMAIL_ADDRESS,
        app_password=GMAIL_APP_PASSWORD,
    )
    print(f"Email sent: {subject}")

    # --- Persist ---
    if ranked:
        scores = {job.url: score for job, score in ranked}
        store.mark_seen_batch([job for job, _ in ranked], scores)

    # Also mark all new jobs as seen (even those below threshold)
    for job in new_jobs:
        if not store.is_seen(job.url):
            store.mark_seen(job, score=0, emailed=False)

    store.close()
    print("Pipeline complete.")


if __name__ == "__main__":
    run_pipeline()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd job-hunter && python -m pytest tests/test_orchestrator.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add job-hunter/orchestrator.py job-hunter/tests/test_orchestrator.py
git commit -m "feat: orchestrator — scrape, dedup, score, email pipeline"
```

---

### Task 11: GitHub Actions Workflow

**Files:**
- Create: `job-hunter/.github/workflows/daily-jobs.yml`

- [ ] **Step 1: Create the workflow file**

```yaml
# job-hunter/.github/workflows/daily-jobs.yml
name: Daily Job Hunter

on:
  schedule:
    # 5pm ET = 9pm UTC (EDT). During EST it runs at 4pm ET.
    - cron: '0 21 * * *'
  workflow_dispatch:  # manual trigger

permissions:
  contents: write

jobs:
  scrape-and-email:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run job hunter pipeline
        env:
          GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
        run: python orchestrator.py

      - name: Commit updated database
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/jobs.db
          git diff --staged --quiet || git commit -m "chore: update jobs.db [skip ci]"
          git push
```

- [ ] **Step 2: Validate the YAML syntax**

```bash
cd job-hunter && python -c "import yaml; yaml.safe_load(open('.github/workflows/daily-jobs.yml'))" 2>/dev/null || python -c "
import json
# Basic validation: check the file is readable and has expected keys
with open('.github/workflows/daily-jobs.yml') as f:
    content = f.read()
assert 'schedule' in content
assert 'workflow_dispatch' in content
assert 'GMAIL_ADDRESS' in content
assert 'orchestrator.py' in content
print('Workflow file looks valid')
"
```

- [ ] **Step 3: Commit**

```bash
git add job-hunter/.github/workflows/daily-jobs.yml
git commit -m "feat: GitHub Actions workflow — daily cron at 5pm ET"
```

---

### Task 12: Integration Smoke Test & Package Fix

**Files:**
- Possibly rename: `job-hunter/email/` → `job-hunter/mailer/` (if name collision)
- Create: `job-hunter/tests/test_integration.py`

- [ ] **Step 1: Check for email package name collision**

```bash
cd job-hunter && python -c "from email.template import render_email; print('OK')"
```

If this fails with an import error about `email.mime` or stdlib confusion, rename `email/` to `mailer/` and update all imports:

```bash
# Only run if the above check fails:
mv email mailer
# Then update imports in: orchestrator.py, tests/test_template.py, tests/test_sender.py, tests/test_orchestrator.py
# Change "from email.template" → "from mailer.template"
# Change "from email.sender" → "from mailer.sender"
# Change "import email.sender" → "import mailer.sender"
```

- [ ] **Step 2: Write integration smoke test**

```python
# job-hunter/tests/test_integration.py
"""Smoke test: exercises the full pipeline with mocked scrapers and email."""
import os
import tempfile
from unittest.mock import patch, MagicMock

from models import Job
from orchestrator import run_pipeline


def _make_jobs():
    return [
        Job(
            title="Senior Product Analyst",
            company="Stripe",
            location="Remote",
            url="https://linkedin.com/jobs/view/111",
            source="linkedin",
            posted_date="2026-04-28",
            salary="$140k",
            description="SQL, Python, A/B testing, experimentation, funnel analysis. Fintech payments company.",
        ),
        Job(
            title="Analytics Lead",
            company="Cash App",
            location="San Francisco, CA",
            url="https://indeed.com/viewjob?jk=222",
            source="indeed",
            posted_date="2026-04-28",
            salary=None,
            description="Looker, DBT, data modeling, causal inference. Financial services.",
        ),
        Job(
            title="Software Engineer",
            company="Google",
            location="Seattle, WA",
            url="https://linkedin.com/jobs/view/333",
            source="linkedin",
            posted_date="2026-04-28",
            salary=None,
            description="Java, microservices, system design interviews.",
        ),
    ]


@patch("orchestrator.send_email")
@patch("orchestrator.IndeedScraper")
@patch("orchestrator.LinkedInScraper")
def test_full_pipeline_smoke(mock_li_cls, mock_indeed_cls, mock_send):
    all_jobs = _make_jobs()

    mock_li = MagicMock()
    mock_li.scrape.return_value = [j for j in all_jobs if j.source == "linkedin"]
    mock_li_cls.return_value = mock_li

    mock_indeed = MagicMock()
    mock_indeed.scrape.return_value = [j for j in all_jobs if j.source == "indeed"]
    mock_indeed_cls.return_value = mock_indeed

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        run_pipeline(db_path=db_path)

    # Email was sent
    mock_send.assert_called_once()
    kwargs = mock_send.call_args[1] if mock_send.call_args[1] else {}
    args = mock_send.call_args[0] if mock_send.call_args[0] else ()

    # Subject should mention listings
    subject = kwargs.get("subject", args[0] if args else "")
    assert "Job Hunter Daily" in subject

    # HTML body should contain the good jobs, not the SWE one
    html_body = kwargs.get("html_body", args[1] if len(args) > 1 else "")
    assert "Senior Product Analyst" in html_body
    assert "Analytics Lead" in html_body
    assert "Software Engineer" not in html_body
```

- [ ] **Step 3: Run full test suite**

```bash
cd job-hunter && python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add job-hunter/tests/test_integration.py
git commit -m "test: integration smoke test — full pipeline with mocked I/O"
```

---

### Task 13: Setup Instructions & First Run

**Files:**
- None (manual steps)

- [ ] **Step 1: Create a new GitHub repo for job-hunter**

```bash
cd job-hunter
git init
git add .
git commit -m "feat: job hunter v1 — daily job scraping and email pipeline"
```

Then on GitHub: create a new repo called `job-hunter` (private).

```bash
git remote add origin https://github.com/<your-username>/job-hunter.git
git branch -M main
git push -u origin main
```

- [ ] **Step 2: Configure GitHub secrets**

In the GitHub repo: Settings → Secrets and variables → Actions → New repository secret:
- `GMAIL_ADDRESS` = `azhang2100@gmail.com`
- `GMAIL_APP_PASSWORD` = (generate at https://myaccount.google.com/apppasswords — requires 2FA enabled)

- [ ] **Step 3: Trigger a manual test run**

In GitHub: Actions tab → "Daily Job Hunter" → "Run workflow" → Run.

Watch the logs. Verify:
- Pipeline runs without crashing
- Email arrives at inbox
- `jobs.db` is committed back to repo

- [ ] **Step 4: Verify daily schedule**

After the manual run succeeds, the cron schedule will trigger automatically at 9pm UTC (5pm ET) daily. Check the next day that it ran and the email arrived.

- [ ] **Step 5: Commit any fixes from the manual run**

```bash
git add -A
git commit -m "fix: address issues found during first manual run"
```
