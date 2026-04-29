# tests/test_scorer.py
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
    assert score >= 35


def test_score_keyword_title_match():
    job = _make_job(title="Business Analytics Lead")
    score = score_job(job)
    assert score >= 25


def test_score_related_title_match():
    job = _make_job(title="Data Analyst")
    score = score_job(job)
    assert score >= 15


def test_score_no_title_match():
    job = _make_job(title="Nurse Practitioner", description="Healthcare role.")
    score = score_job(job)
    assert score < 30


def test_hard_filter_rejects_swe():
    job = _make_job(title="Software Engineer")
    score = score_job(job)
    assert score == -1


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
    assert len(ranked) <= 2
    assert all(score >= 30 for _, score in ranked)
    assert all("Software Engineer" not in job.title for job, _ in ranked)


def test_filter_and_rank_respects_min_score():
    jobs = [_make_job(title="Nurse Practitioner", description="Healthcare.")]
    ranked = filter_and_rank(jobs, top_n=20, min_score=30)
    assert len(ranked) == 0
