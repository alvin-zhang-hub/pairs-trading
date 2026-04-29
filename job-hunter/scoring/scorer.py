# scoring/scorer.py
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
