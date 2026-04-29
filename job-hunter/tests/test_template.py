from models import Job
from mailer.template import render_email


def _make_scored_jobs():
    return [
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
