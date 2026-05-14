import csv
import json
import os
from datetime import date

import pandas as pd

from lighthouse.writer import write_scan_results


def make_results():
    return pd.DataFrame([
        {
            "ticker": "ABCD",
            "stage2_flag": True,
            "price": 25.5,
            "mcap": 1_500_000_000,
            "adv_20d_dollar": 20_000_000,
            "weekly_close_above_30w_ma": True,
            "ma_slope_positive": True,
            "golden_cross": True,
            "near_52w_high": True,
            "breakout_volume": True,
        },
        {
            "ticker": "EFGH",
            "stage2_flag": True,
            "price": 8.10,
            "mcap": 350_000_000,
            "adv_20d_dollar": 6_500_000,
            "weekly_close_above_30w_ma": True,
            "ma_slope_positive": True,
            "golden_cross": True,
            "near_52w_high": True,
            "breakout_volume": True,
        },
    ])


class TestWriteScanResults:
    def test_writes_csv_with_expected_rows(self, tmp_path):
        df = make_results()
        write_scan_results(df, output_dir=str(tmp_path))
        csv_path = tmp_path / "scanner_latest.csv"
        assert csv_path.exists()
        loaded = pd.read_csv(csv_path)
        assert list(loaded["ticker"]) == ["ABCD", "EFGH"]
        assert loaded.loc[0, "stage2_flag"] in (True, "True", 1)

    def test_writes_json_cache(self, tmp_path):
        df = make_results()
        write_scan_results(df, output_dir=str(tmp_path))
        cache_path = tmp_path / "scanner_cache.json"
        assert cache_path.exists()
        with open(cache_path) as f:
            data = json.load(f)
        assert "generated_at" in data
        assert "results" in data
        assert len(data["results"]) == 2
        assert data["results"][0]["ticker"] == "ABCD"

    def test_cache_records_scan_timestamp(self, tmp_path):
        df = make_results()
        write_scan_results(df, output_dir=str(tmp_path))
        with open(tmp_path / "scanner_cache.json") as f:
            data = json.load(f)
        # ISO-format timestamp; just confirm it parses
        from datetime import datetime
        datetime.fromisoformat(data["generated_at"])

    def test_overwrites_existing_latest_csv(self, tmp_path):
        write_scan_results(make_results(), output_dir=str(tmp_path))
        df2 = pd.DataFrame([{
            "ticker": "ONLY1",
            "stage2_flag": True,
            "price": 10.0,
            "mcap": 1e9,
            "adv_20d_dollar": 1e7,
            "weekly_close_above_30w_ma": True,
            "ma_slope_positive": True,
            "golden_cross": True,
            "near_52w_high": True,
            "breakout_volume": True,
        }])
        write_scan_results(df2, output_dir=str(tmp_path))
        loaded = pd.read_csv(tmp_path / "scanner_latest.csv")
        assert list(loaded["ticker"]) == ["ONLY1"]

    def test_writes_dated_archive_when_close_of_day(self, tmp_path):
        df = make_results()
        write_scan_results(df, output_dir=str(tmp_path), close_of_day=True)
        archive_dir = tmp_path / "scanner_archive"
        assert archive_dir.exists()
        files = list(archive_dir.iterdir())
        assert len(files) == 1
        assert files[0].name == f"scanner_{date.today().isoformat()}_close.csv"

    def test_does_not_write_archive_by_default(self, tmp_path):
        write_scan_results(make_results(), output_dir=str(tmp_path))
        archive_dir = tmp_path / "scanner_archive"
        # Directory may exist (we mkdir defensively) but should be empty
        assert not archive_dir.exists() or len(list(archive_dir.iterdir())) == 0

    def test_handles_empty_results(self, tmp_path):
        empty = pd.DataFrame(columns=[
            "ticker", "stage2_flag", "price", "mcap", "adv_20d_dollar",
            "weekly_close_above_30w_ma", "ma_slope_positive", "golden_cross",
            "near_52w_high", "breakout_volume",
        ])
        write_scan_results(empty, output_dir=str(tmp_path))
        csv_path = tmp_path / "scanner_latest.csv"
        cache_path = tmp_path / "scanner_cache.json"
        assert csv_path.exists() and cache_path.exists()
        with open(cache_path) as f:
            data = json.load(f)
        assert data["results"] == []
