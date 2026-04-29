# tests/test_indeed.py
from unittest.mock import patch, MagicMock

from scrapers.indeed import IndeedScraper

SAMPLE_HTML = """
<html>
<body>
<div id="mosaic-provider-jobcards">
  <ul>
    <li>
      <div class="job_seen_beacon" data-jk="abc123">
        <h2 class="jobTitle">
          <a href="/viewjob?jk=abc123">
            <span>Product Analytics Lead</span>
          </a>
        </h2>
        <span data-testid="company-name">Cash App</span>
        <div data-testid="text-location">San Francisco, CA</div>
        <span class="date">Posted 1 day ago</span>
      </div>
    </li>
    <li>
      <div class="job_seen_beacon" data-jk="def456">
        <h2 class="jobTitle">
          <a href="/viewjob?jk=def456">
            <span>Senior Growth Analyst</span>
          </a>
        </h2>
        <span data-testid="company-name">Duolingo</span>
        <div data-testid="text-location">Remote</div>
        <span class="date">Posted today</span>
      </div>
    </li>
  </ul>
</div>
</body>
</html>
"""


def _mock_response(html, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = html
    return resp


@patch("scrapers.indeed.time.sleep")
@patch("scrapers.indeed.requests.get")
def test_scrape_parses_indeed_html(mock_get, mock_sleep):
    mock_get.return_value = _mock_response(SAMPLE_HTML)
    scraper = IndeedScraper()
    jobs = scraper.scrape(["Product Analyst"], ["San Francisco"])
    assert len(jobs) >= 2
    assert jobs[0].title == "Product Analytics Lead"
    assert jobs[0].company == "Cash App"
    assert jobs[0].source == "indeed"
    assert "indeed.com" in jobs[0].url


@patch("scrapers.indeed.time.sleep")
@patch("scrapers.indeed.requests.get")
def test_scrape_returns_empty_on_failure(mock_get, mock_sleep):
    mock_get.side_effect = Exception("Timeout")
    scraper = IndeedScraper()
    jobs = scraper.scrape(["Product Analyst"], ["Remote"])
    assert jobs == []


@patch("scrapers.indeed.time.sleep")
@patch("scrapers.indeed.requests.get")
def test_scrape_deduplicates_across_queries(mock_get, mock_sleep):
    mock_get.return_value = _mock_response(SAMPLE_HTML)
    scraper = IndeedScraper()
    jobs = scraper.scrape(["Product Analyst", "Growth Analyst"], ["Remote"])
    urls = [j.url for j in jobs]
    assert len(urls) == len(set(urls))
