# tests/test_orchestrator.py
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
        run_pipeline(db_path=db_path)
        assert mock_send.call_count == 1

        mock_send.reset_mock()
        run_pipeline(db_path=db_path)
        assert mock_send.call_count == 1


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

    mock_send.assert_called_once()
