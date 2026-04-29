# scoring/profile.py

# Exact target titles — score 35 for exact match (case-insensitive)
TARGET_TITLES = [
    "product analyst",
    "senior product analyst",
    "analytics lead",
    "analytics manager",
    "head of analytics",
    "analytics engineer",
    "growth analyst",
    "product manager",
    "strategy & operations",
    "chief of staff",
    "revops",
]

TITLE_KEYWORDS = [
    "analytics",
    "product analyst",
    "product manager",
    "growth",
    "strategy",
    "operations",
    "revops",
]

RELATED_TITLES = [
    "data analyst",
    "business analyst",
    "business intelligence",
    "insights analyst",
    "decision scientist",
]

PROFILE_SKILLS = [
    "sql",
    "python",
    "dbt",
    "a/b testing",
    "experimentation",
    "causal inference",
    "funnel analysis",
    "data modeling",
    "databricks",
    "looker",
    "tableau",
    "power bi",
    "cohort analysis",
]

SENIORITY_TERMS = {
    "senior": 15,
    "lead": 15,
    "manager": 15,
    "head": 15,
    "director": 15,
    "staff": 10,
}
SENIORITY_DEFAULT = 5

HARD_FILTER_TITLES = [
    "machine learning engineer",
    "software engineer",
    "sde",
    "data engineer",
    "intern",
    "junior",
    "entry level",
]

HARD_FILTER_DESCRIPTION = [
    "phd required",
    "5+ years ml/ai experience",
    "deep learning frameworks",
    "system design interviews",
]

INDUSTRY_TIERS = {
    "fintech": 10,
    "financial services": 10,
    "payments": 10,
    "banking": 10,
    "neobank": 10,
    "e-commerce": 7,
    "ecommerce": 7,
    "retail": 7,
    "marketplace": 7,
    "tech": 5,
    "saas": 5,
    "software": 5,
    "other": 2,
}
