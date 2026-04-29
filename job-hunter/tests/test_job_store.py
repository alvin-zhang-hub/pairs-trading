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
