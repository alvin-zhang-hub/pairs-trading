import math

import pandas as pd
import pytest

from lighthouse.filters import apply_liquidity_gate, passes_gate


def make_row(**overrides):
    base = {
        "ticker": "ABCD",
        "mcap": 1_500_000_000,
        "price": 25.0,
        "adv_20d_dollar": 20_000_000,
        "industry": "Software—Application",
    }
    base.update(overrides)
    return base


def make_df(*rows):
    return pd.DataFrame(rows)


class TestPassesGate:
    def test_passes_when_all_thresholds_met(self):
        row = make_row()
        assert passes_gate(row) is True

    def test_excludes_mcap_at_or_above_5b(self):
        assert passes_gate(make_row(mcap=5_000_000_000)) is False
        assert passes_gate(make_row(mcap=6_000_000_000)) is False

    def test_passes_mcap_just_under_5b(self):
        assert passes_gate(make_row(mcap=4_999_999_999)) is True

    def test_excludes_price_below_5(self):
        assert passes_gate(make_row(price=4.99)) is False

    def test_passes_price_at_5(self):
        assert passes_gate(make_row(price=5.00)) is True

    def test_excludes_adv_below_5m(self):
        assert passes_gate(make_row(adv_20d_dollar=4_999_999)) is False

    def test_passes_adv_at_5m(self):
        assert passes_gate(make_row(adv_20d_dollar=5_000_000)) is True

    def test_excludes_when_mcap_missing(self):
        assert passes_gate(make_row(mcap=None)) is False
        assert passes_gate(make_row(mcap=math.nan)) is False

    def test_excludes_when_price_missing(self):
        assert passes_gate(make_row(price=None)) is False

    def test_excludes_when_adv_missing(self):
        assert passes_gate(make_row(adv_20d_dollar=None)) is False

    def test_excludes_biotech_industry(self):
        assert passes_gate(make_row(industry="Biotechnology")) is False

    def test_excludes_biotech_case_insensitive(self):
        assert passes_gate(make_row(industry="biotechnology")) is False

    def test_excludes_any_industry_containing_biotech(self):
        # Some yfinance values are formatted differently; we match by keyword
        assert passes_gate(make_row(industry="Biotech & Therapeutics")) is False

    def test_passes_when_industry_missing(self):
        # Don't penalize unknowns — yfinance sometimes returns None
        assert passes_gate(make_row(industry=None)) is True

    def test_passes_non_excluded_industry(self):
        assert passes_gate(make_row(industry="Software—Infrastructure")) is True
        assert passes_gate(make_row(industry="Semiconductors")) is True
        # Big pharma is NOT excluded by default — it trades like a normal stock
        assert passes_gate(make_row(industry="Drug Manufacturers—General")) is True


class TestApplyLiquidityGate:
    def test_keeps_passing_rows_and_drops_failing(self):
        df = make_df(
            make_row(ticker="KEEP1"),
            make_row(ticker="DROP_MCAP", mcap=10_000_000_000),
            make_row(ticker="DROP_PRICE", price=2.5),
            make_row(ticker="DROP_ADV", adv_20d_dollar=1_000_000),
            make_row(ticker="KEEP2", price=8.0, mcap=300_000_000, adv_20d_dollar=8_000_000),
        )
        out = apply_liquidity_gate(df)
        assert list(out["ticker"]) == ["KEEP1", "KEEP2"]

    def test_returns_empty_when_no_rows_pass(self):
        df = make_df(make_row(price=1.0), make_row(mcap=8_000_000_000))
        out = apply_liquidity_gate(df)
        assert len(out) == 0

    def test_handles_empty_input(self):
        df = pd.DataFrame(columns=["ticker", "mcap", "price", "adv_20d_dollar"])
        out = apply_liquidity_gate(df)
        assert len(out) == 0

    def test_does_not_mutate_input(self):
        df = make_df(make_row(), make_row(ticker="BAD", price=1.0))
        before = df.copy()
        apply_liquidity_gate(df)
        pd.testing.assert_frame_equal(df, before)

    def test_resets_index_after_filtering(self):
        df = make_df(
            make_row(ticker="A"),
            make_row(ticker="DROP", price=1.0),
            make_row(ticker="C"),
        )
        out = apply_liquidity_gate(df)
        assert list(out.index) == [0, 1]
