import json

import pandas as pd
import pytest

from lighthouse.ranker import load_prior_tickers, mark_new_today


def _write_cache(tmp_path, tickers):
    path = tmp_path / "scanner_cache.json"
    payload = {
        "generated_at": "2026-05-12T22:00:00+00:00",
        "results": [{"ticker": t} for t in tickers],
    }
    path.write_text(json.dumps(payload))
    return str(path)


class TestLoadPriorTickers:
    def test_returns_empty_set_when_file_missing(self, tmp_path):
        assert load_prior_tickers(str(tmp_path / "nope.json")) == set()

    def test_extracts_tickers_from_cache(self, tmp_path):
        path = _write_cache(tmp_path, ["AAPL", "NVDA", "MSFT"])
        assert load_prior_tickers(path) == {"AAPL", "NVDA", "MSFT"}

    def test_handles_empty_results(self, tmp_path):
        path = _write_cache(tmp_path, [])
        assert load_prior_tickers(path) == set()

    def test_handles_malformed_cache(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json at all")
        assert load_prior_tickers(str(path)) == set()

    def test_handles_missing_results_key(self, tmp_path):
        path = tmp_path / "cache.json"
        path.write_text(json.dumps({"generated_at": "now"}))
        assert load_prior_tickers(str(path)) == set()


class TestMarkNewToday:
    def test_all_new_when_no_prior_cache(self, tmp_path):
        df = pd.DataFrame([{"ticker": "A"}, {"ticker": "B"}])
        out = mark_new_today(df, prior_cache_path=str(tmp_path / "missing.json"))
        assert out["new_today"].tolist() == [True, True]

    def test_keeps_old_marks_false(self, tmp_path):
        path = _write_cache(tmp_path, ["A", "B"])
        df = pd.DataFrame([{"ticker": "A"}, {"ticker": "B"}, {"ticker": "C"}])
        out = mark_new_today(df, prior_cache_path=path)
        assert out["new_today"].tolist() == [False, False, True]

    def test_does_not_mutate_input(self, tmp_path):
        path = _write_cache(tmp_path, ["A"])
        df = pd.DataFrame([{"ticker": "A"}, {"ticker": "B"}])
        before = df.copy()
        mark_new_today(df, prior_cache_path=path)
        pd.testing.assert_frame_equal(df, before)

    def test_handles_empty_dataframe(self, tmp_path):
        df = pd.DataFrame(columns=["ticker"])
        out = mark_new_today(df, prior_cache_path=str(tmp_path / "x.json"))
        assert "new_today" in out.columns
        assert len(out) == 0
