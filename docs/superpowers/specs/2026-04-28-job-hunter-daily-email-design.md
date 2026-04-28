# Job Hunter — Daily Email Pipeline

**Date:** 2026-04-28
**Author:** Alvin Zhang
**Status:** Design approved

---

## Overview

Automated daily pipeline that scrapes job listings from LinkedIn and Indeed, deduplicates against previously seen listings, scores them against Alvin's profile, and emails the top 20 new matches at 5pm ET. Runs via GitHub Actions on a scheduled cron.

## Project Structure

```
job-hunter/
  scrapers/
    base.py              # Abstract scraper interface
    linkedin.py          # LinkedIn scraper
    indeed.py            # Indeed scraper
  scoring/
    scorer.py            # Scoring engine + hard filters
    profile.py           # Skills, titles, exclusions config
  email/
    sender.py            # Gmail SMTP sender
    template.py          # HTML email formatting
  store/
    job_store.py         # SQLite persistence — seen jobs, dedup
  models.py              # Job dataclass shared across modules
  config.py              # Search params, locations, email settings
  orchestrator.py        # Main pipeline: scrape → dedup → score → email
  requirements.txt
  data/
    jobs.db              # SQLite database (committed to git)
  .github/
    workflows/
      daily-jobs.yml     # GitHub Actions cron schedule
```

## Data Model

Shared `Job` dataclass used across all modules:

```python
@dataclass
class Job:
    title: str
    company: str
    location: str
    url: str              # direct link to listing
    source: str           # "linkedin" or "indeed"
    posted_date: str | None
    salary: str | None
    description: str      # used for scoring, not included in email
```

## Scrapers

### Interface

Each scraper implements:

```python
class BaseScraper(ABC):
    def scrape(self, search_terms: list[str], locations: list[str]) -> list[Job]:
        ...
```

### LinkedIn Scraper

- Hits LinkedIn's public job search pages (`linkedin.com/jobs/search/`)
- Uses `requests` + `BeautifulSoup` with rotating User-Agent headers
- Pagination via offset parameter
- Request delays of 2-5 seconds between pages to avoid blocking
- Limitations: LinkedIn may return fewer results without auth; markup changes will break the parser

### Indeed Scraper

- Hits Indeed's search pages (`indeed.com/jobs`)
- Uses `requests` + `BeautifulSoup`
- Retry logic and request delays (2-5 seconds between pages)
- Similar anti-bot considerations as LinkedIn

### Search Parameters

**Titles (11):**
- Product Analyst
- Senior Product Analyst
- Analytics Lead
- Analytics Manager
- Head of Analytics
- Analytics Engineer
- Growth Analyst
- Product Manager
- Strategy & Operations
- Chief of Staff
- RevOps

**Locations (7):**
- Remote
- Boston
- Seattle
- New York
- Los Angeles
- San Diego
- San Francisco

**Total queries:** 11 titles x 7 locations = 77 per source, 154 total.

**Estimated runtime:** ~10-15 minutes with delays.

### Failure Handling

If one scraper fails entirely (e.g., LinkedIn blocks the request), the pipeline continues with the other source. The failure is noted in the email footer.

## Scoring Engine

Two-phase system: hard filters (reject) then soft scoring (rank).

### Hard Filters — Instant Reject

A job is rejected if any of these match:

- **Title contains:** "machine learning engineer", "software engineer", "SDE", "data engineer", "intern", "junior", "entry level"
- **Description requires:** "PhD required", "5+ years ML/AI experience", "deep learning frameworks", "system design interviews"

### Soft Scoring — 0 to 100 Points

| Factor | Max Points | Logic |
|--------|-----------|-------|
| Title match | 35 | Exact match to a target title = 35. Title contains a target keyword (e.g., "analytics" in "Business Analytics Lead") = 25. Related title (e.g., "Data Analyst") = 15. No match = 0 |
| Skills overlap | 25 | Count of profile skills (SQL, Python, DBT, A/B testing, experimentation, causal inference, funnel analysis, data modeling, Databricks, Looker, Tableau) found in description |
| Seniority fit | 15 | "Senior", "Lead", "Manager" in title = 15. "Staff" = 10. No seniority indicator = 5 |
| Location match | 15 | Remote = 15, target city = 15, hybrid in target city = 10 |
| Industry bonus | 10 | Fintech/finance keywords = 10, e-commerce = 7, tech = 5, other = 2 |

### Selection

- Top 20 by score are included in the email
- Minimum score threshold of 30 — if fewer than 20 pass, send whatever qualifies
- All scoring weights and filter terms live in `profile.py` for easy tuning

## Job Store (Persistence)

### SQLite Schema

```sql
CREATE TABLE jobs_seen (
    url TEXT PRIMARY KEY,
    title TEXT,
    company TEXT,
    source TEXT,
    first_seen DATE,
    score INTEGER,
    emailed BOOLEAN
);
```

### Dedup Logic

1. Scrape jobs from all sources
2. Check each job's URL against `jobs_seen`
3. Only new (unseen) jobs proceed to scoring
4. After emailing, insert emailed jobs into `jobs_seen`

### Persistence Strategy

The `jobs.db` file is committed to the git repo after each run. The GitHub Actions workflow auto-commits the updated database back to the repo. This provides:
- Persistence between workflow runs
- Built-in backup of every state via git history
- Simple implementation (no external storage needed)

## Email Delivery

### Transport

Gmail SMTP via Python `smtplib` + `email.mime`. Requires a Gmail App Password stored as a GitHub Actions secret.

### Email Format

HTML email with a clean table layout:

```
Subject: Job Hunter Daily — April 28, 2026 (14 new listings)

Hey Alvin,

Here are today's top matches, ranked by fit:

 #  | Score | Title                    | Company    | Location | Link
 1  | 87    | Product Analytics Lead   | Stripe     | Remote   | [Apply →]
 2  | 82    | Senior Product Analyst   | Robinhood  | Boston   | [Apply →]
 3  | 75    | Analytics Manager        | Wayfair    | Boston   | [Apply →]
 ...

---
Sources checked: LinkedIn ✓, Indeed ✓
Total scraped: 243 | New today: 38 | Passed filters: 22
```

### Footer

Includes scraper health status (which sources succeeded/failed), total counts for transparency and calibration.

### Secrets Required

- `GMAIL_ADDRESS` — azhang2100@gmail.com
- `GMAIL_APP_PASSWORD` — generated from Google account settings

## GitHub Actions Workflow

### Schedule

```yaml
on:
  schedule:
    - cron: '0 21 * * *'   # 5pm ET (9pm UTC, EDT offset)
  workflow_dispatch:         # manual trigger for testing
```

### Steps

1. Checkout repo (includes `data/jobs.db`)
2. Set up Python 3.13 + `pip install -r requirements.txt`
3. Run `python orchestrator.py`
4. Commit and push updated `data/jobs.db` back to repo
5. If orchestrator fails, send a short error notification email

### Resource Usage

- Estimated runtime: ~15 minutes per run
- GitHub Actions free tier: 2,000 min/month
- Monthly usage: ~450 minutes (well within budget)

## Dependencies

- `requests` — HTTP requests
- `beautifulsoup4` — HTML parsing
- `lxml` — fast HTML parser backend

Standard library only for everything else (`smtplib`, `sqlite3`, `dataclasses`, `email.mime`).

## Known Risks and Limitations

1. **Scraper fragility:** LinkedIn and Indeed can change markup at any time, breaking parsers. Modular design makes fixing isolated to one file.
2. **Anti-bot blocking:** Both sites actively block scrapers. Rotating User-Agents and delays mitigate this, but blocking is still possible. The pipeline degrades gracefully (continues with working sources).
3. **LinkedIn result limits:** Public (non-authenticated) LinkedIn search returns fewer results than logged-in search.
4. **Timezone drift:** The cron schedule uses UTC. EDT/EST shifts will move delivery time by 1 hour during daylight saving transitions.
5. **No application tracking:** V1 only tracks seen/emailed jobs. Tracking application status is a potential future enhancement.

## Future Enhancements (Not in V1)

- Additional sources: Wellfound, Greenhouse/Lever boards, Google Jobs API
- LLM-based scoring (Claude API) for more nuanced fit evaluation
- Application tracking (applied, interviewing, rejected)
- Weekly summary digest in addition to daily email
