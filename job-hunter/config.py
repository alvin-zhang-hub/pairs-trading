# job-hunter/config.py
import os

SEARCH_TITLES = [
    "Product Analyst",
    "Senior Product Analyst",
    "Analytics Lead",
    "Analytics Manager",
    "Head of Analytics",
    "Analytics Engineer",
    "Growth Analyst",
    "Product Manager",
    "Strategy & Operations",
    "Chief of Staff",
    "RevOps",
]

SEARCH_LOCATIONS = [
    "Remote",
    "Boston",
    "Seattle",
    "New York",
    "Los Angeles",
    "San Diego",
    "San Francisco",
]

EMAIL_RECIPIENT = os.environ.get("GMAIL_ADDRESS", "azhang2100@gmail.com")
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "azhang2100@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

TOP_N = 20
MIN_SCORE = 30

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "jobs.db")

REQUEST_DELAY_MIN = 2
REQUEST_DELAY_MAX = 5
