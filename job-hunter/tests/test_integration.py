# tests/test_integration.py
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

    # Get the call arguments
    call_args = mock_send.call_args
    # send_email is called with keyword arguments
    subject = call_args.kwargs.get("subject", call_args[1].get("subject", "")) if call_args.kwargs else call_args[1].get("subject", "")
    html_body = call_args.kwargs.get("html_body", call_args[1].get("html_body", "")) if call_args.kwargs else call_args[1].get("html_body", "")

    assert "Job Hunter Daily" in subject

    # HTML body should contain the good jobs, not the SWE one
    assert "Senior Product Analyst" in html_body
    assert "Analytics Lead" in html_body
    # Software Engineer should be hard-filtered out
    assert "Software Engineer" not in html_body
