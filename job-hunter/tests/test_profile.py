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
    assert "product analyst" in TARGET_TITLES
    assert "analytics lead" in TARGET_TITLES
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
