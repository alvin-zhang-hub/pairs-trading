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
