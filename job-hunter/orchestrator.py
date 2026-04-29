# orchestrator.py
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
from mailer.template import render_email
from mailer.sender import send_email


def run_pipeline(db_path: str | None = None):
    if db_path is None:
        db_path = DB_PATH

    store = JobStore(db_path)
    all_jobs: list[Job] = []
    source_status: dict[str, bool] = {}

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

    new_jobs = store.filter_new(all_jobs)
    new_today = len(new_jobs)
    print(f"New jobs after dedup: {new_today}")

    ranked = filter_and_rank(new_jobs, top_n=TOP_N, min_score=MIN_SCORE)
    passed_filters = len(ranked)
    print(f"Jobs passing filters: {passed_filters}")

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

    if ranked:
        scores = {job.url: score for job, score in ranked}
        store.mark_seen_batch([job for job, _ in ranked], scores)

    for job in new_jobs:
        if not store.is_seen(job.url):
            store.mark_seen(job, score=0, emailed=False)

    store.close()
    print("Pipeline complete.")


if __name__ == "__main__":
    run_pipeline()
