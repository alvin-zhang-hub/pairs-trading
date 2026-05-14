import json

import pytest

from lighthouse.dashboard_view import render_scanner_page


def _write_cache(tmp_path, results):
    payload = {
        "generated_at": "2026-05-13T22:00:00+00:00",
        "results": results,
    }
    path = tmp_path / "scanner_cache.json"
    path.write_text(json.dumps(payload))
    return str(path)


def _hit(ticker, **overrides):
    base = {
        "ticker": ticker,
        "stage2_flag": False,
        "score_total": 7,
        "fund_total": 6,
        "combined_score": 13,
        "score_trend": 2,
        "score_relative_strength": 2,
        "score_volume_accumulation": 1,
        "score_volatility_contraction": 0,
        "score_distance_from_high": 2,
        "fund_revenue_growth": 2,
        "fund_margin_expansion": 1,
        "fund_profitability_path": 2,
        "fund_pe_compression": 1,
        "fund_earnings_beat": 0,
        "weekly_close_above_30w_ma": True,
        "ma_slope_positive": True,
        "golden_cross": True,
        "near_52w_high": True,
        "breakout_volume": False,
        "price": 25.50,
        "mcap": 1_500_000_000,
        "adv_20d_dollar": 20_000_000,
        "sector": "Technology",
        "industry": "Software - Application",
        "business_summary": "A sample company that does sample things.",
        "themes": [],
        "new_today": False,
    }
    base.update(overrides)
    return base


# -----------------------------------------------------------------------------
# Empty / missing cache
# -----------------------------------------------------------------------------

class TestRenderScannerPageMissingData:
    def test_renders_empty_state_when_cache_missing(self, tmp_path):
        html = render_scanner_page(str(tmp_path / "nope.json"))
        assert "<html" in html.lower()
        assert "no scan" in html.lower() or "no results" in html.lower()

    def test_renders_empty_state_when_results_empty(self, tmp_path):
        path = _write_cache(tmp_path, [])
        html = render_scanner_page(path)
        assert "<html" in html.lower()
        assert "no scan" in html.lower() or "no results" in html.lower()


# -----------------------------------------------------------------------------
# Core rendering
# -----------------------------------------------------------------------------

class TestRenderScannerPageBasics:
    def test_contains_each_ticker(self, tmp_path):
        path = _write_cache(tmp_path, [_hit("AAPL"), _hit("NVDA"), _hit("MSFT")])
        html = render_scanner_page(path)
        for t in ["AAPL", "NVDA", "MSFT"]:
            assert t in html

    def test_shows_scan_timestamp(self, tmp_path):
        path = _write_cache(tmp_path, [_hit("AAPL")])
        html = render_scanner_page(path)
        # Just confirm a date or "Updated" label appears
        assert "2026" in html or "Updated" in html or "Last scan" in html

    def test_shows_hit_count(self, tmp_path):
        path = _write_cache(tmp_path, [_hit("A"), _hit("B"), _hit("C")])
        html = render_scanner_page(path)
        assert "3" in html

    def test_marks_stage2_hits_visually(self, tmp_path):
        path = _write_cache(tmp_path, [_hit("STAGE2", stage2_flag=True), _hit("NOSTAGE2")])
        html = render_scanner_page(path)
        # Some visual indicator for Stage 2 — check a row that has it differs from one that doesn't
        # We expect a badge/icon/word like "Stage 2" or "✓" near the STAGE2 ticker
        stage2_index = html.find("STAGE2")
        nostage2_index = html.find("NOSTAGE2")
        # In a narrow window around the STAGE2 row, we'd expect a badge string
        window = html[stage2_index:stage2_index + 300]
        assert ("Stage 2" in window) or ("✓" in window) or ("stage2" in window.lower())

    def test_highlights_new_today_rows(self, tmp_path):
        path = _write_cache(tmp_path, [_hit("FRESH", new_today=True), _hit("OLD", new_today=False)])
        html = render_scanner_page(path)
        # Look for "new" indicator near FRESH row
        fresh_index = html.find("FRESH")
        window = html[fresh_index:fresh_index + 300]
        assert ("NEW" in window.upper()) or ("new_today" in window.lower())

    def test_shows_business_summary(self, tmp_path):
        path = _write_cache(tmp_path, [_hit("XYZ", business_summary="A unique description string")])
        html = render_scanner_page(path)
        assert "unique description string" in html

    def test_shows_theme_tags(self, tmp_path):
        path = _write_cache(tmp_path, [_hit("AAA", themes=["ai-infra", "semis"])])
        html = render_scanner_page(path)
        assert "ai-infra" in html
        assert "semis" in html


# -----------------------------------------------------------------------------
# Filters
# -----------------------------------------------------------------------------

class TestRenderScannerPageFilters:
    def test_filter_by_sector(self, tmp_path):
        path = _write_cache(tmp_path, [
            _hit("TECH1", sector="Technology"),
            _hit("FIN1", sector="Financial Services"),
        ])
        html = render_scanner_page(path, filters={"sector": "Technology"})
        # TECH1 should appear in the data table; FIN1 should not appear as a row
        # (it may still appear in a "sector filter" dropdown, hence we check for
        # presence near a recognizable price string)
        tech_window = html[html.find("TECH1"):html.find("TECH1") + 200] if "TECH1" in html else ""
        fin_loc = html.find("FIN1")
        # TECH1 must be present
        assert "TECH1" in html
        # If FIN1 appears at all, it should only be in select/option (filter dropdown)
        if fin_loc != -1:
            window = html[max(0, fin_loc - 50):fin_loc + 50]
            assert "option" in window.lower()

    def test_filter_by_theme(self, tmp_path):
        path = _write_cache(tmp_path, [
            _hit("ALPHA", themes=["ai-infra"]),
            _hit("BETA", themes=["nuclear"]),
        ])
        html = render_scanner_page(path, filters={"theme": "ai-infra"})
        assert "ALPHA" in html
        # BETA's row should not appear; if BETA appears, only in a filter dropdown
        beta_loc = html.find("BETA")
        if beta_loc != -1:
            window = html[max(0, beta_loc - 50):beta_loc + 50]
            assert "option" in window.lower()

    def test_filter_stage2_only(self, tmp_path):
        path = _write_cache(tmp_path, [
            _hit("S2", stage2_flag=True),
            _hit("NOTS2", stage2_flag=False),
        ])
        html = render_scanner_page(path, filters={"stage2_only": True})
        assert "S2" in html
        assert "NOTS2" not in html


# -----------------------------------------------------------------------------
# Sorting
# -----------------------------------------------------------------------------

class TestRenderScannerPageSorting:
    def test_orders_by_combined_score_descending_by_default(self, tmp_path):
        path = _write_cache(tmp_path, [
            _hit("LOW", combined_score=8),
            _hit("HIGH", combined_score=14),
            _hit("MID", combined_score=11),
        ])
        html = render_scanner_page(path)
        high_pos = html.find("HIGH")
        mid_pos = html.find("MID")
        low_pos = html.find("LOW")
        assert high_pos < mid_pos < low_pos
