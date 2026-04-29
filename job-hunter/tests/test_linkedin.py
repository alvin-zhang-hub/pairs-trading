# tests/test_linkedin.py
from unittest.mock import patch, MagicMock

from scrapers.linkedin import LinkedInScraper

SAMPLE_HTML = """
<html>
<body>
<div class="base-card" data-entity-urn="urn:li:jobPosting:12345">
  <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/12345">
  </a>
  <h3 class="base-search-card__title">Senior Product Analyst</h3>
  <h4 class="base-search-card__subtitle">
    <a>Stripe</a>
  </h4>
  <span class="job-search-card__location">Remote</span>
  <time class="job-search-card__listdate" datetime="2026-04-27"></time>
</div>
<div class="base-card" data-entity-urn="urn:li:jobPosting:67890">
  <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/67890">
  </a>
  <h3 class="base-search-card__title">Analytics Manager</h3>
  <h4 class="base-search-card__subtitle">
    <a>Robinhood</a>
  </h4>
  <span class="job-search-card__location">New York, NY</span>
  <time class="job-search-card__listdate" datetime="2026-04-26"></time>
</div>
</body>
</html>
"""


def _mock_response(html, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = html
    return resp


@patch("scrapers.linkedin.time.sleep")
@patch("scrapers.linkedin.requests.get")
def test_scrape_parses_linkedin_html(mock_get, mock_sleep):
    mock_get.return_value = _mock_response(SAMPLE_HTML)
    scraper = LinkedInScraper()
    jobs = scraper.scrape(["Product Analyst"], ["Remote"])
    assert len(jobs) >= 2
    assert jobs[0].title == "Senior Product Analyst"
    assert jobs[0].company == "Stripe"
    assert jobs[0].source == "linkedin"
    assert "linkedin.com/jobs/view/12345" in jobs[0].url


@patch("scrapers.linkedin.time.sleep")
@patch("scrapers.linkedin.requests.get")
def test_scrape_returns_empty_on_failure(mock_get, mock_sleep):
    mock_get.side_effect = Exception("Connection refused")
    scraper = LinkedInScraper()
    jobs = scraper.scrape(["Product Analyst"], ["Remote"])
    assert jobs == []


@patch("scrapers.linkedin.time.sleep")
@patch("scrapers.linkedin.requests.get")
def test_scrape_deduplicates_across_queries(mock_get, mock_sleep):
    mock_get.return_value = _mock_response(SAMPLE_HTML)
    scraper = LinkedInScraper()
    jobs = scraper.scrape(["Product Analyst", "Analytics Manager"], ["Remote"])
    urls = [j.url for j in jobs]
    assert len(urls) == len(set(urls))
