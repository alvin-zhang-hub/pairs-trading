import pandas as pd
import pytest

from lighthouse.fundamentals import (
    growth_inflection_score,
    score_earnings_beat,
    score_margin_expansion,
    score_pe_compression,
    score_profitability_path,
    score_revenue_growth,
)


def make_qf(
    revenue=(100, 90, 80, 75, 65),
    gross=None,
    op_income=None,
):
    """Build a synthetic quarterly_financials DataFrame in yfinance format.

    Input lists are most-recent-first (matching yfinance). Gross profit and
    operating income default to plausible ratios (60% / 20% of revenue).
    """
    rev = list(revenue)
    n = len(rev)
    gp = list(gross) if gross is not None else [r * 0.60 for r in rev]
    op = list(op_income) if op_income is not None else [r * 0.20 for r in rev]
    dates = [pd.Timestamp("2026-03-31") - pd.DateOffset(months=3 * i) for i in range(n)]
    return pd.DataFrame(
        {dates[i]: [rev[i], gp[i], op[i]] for i in range(n)},
        index=["Total Revenue", "Gross Profit", "Operating Income"],
    )


def make_qcf(fcf=(10, 8, 5, 2, -2)):
    fcf = list(fcf)
    n = len(fcf)
    dates = [pd.Timestamp("2026-03-31") - pd.DateOffset(months=3 * i) for i in range(n)]
    return pd.DataFrame({dates[i]: [fcf[i]] for i in range(n)}, index=["Free Cash Flow"])


# -----------------------------------------------------------------------------
# 1. Revenue growth
# -----------------------------------------------------------------------------

class TestScoreRevenueGrowth:
    def test_returns_3_for_growth_above_40pct(self):
        # 100 / 65 - 1 = 53.8%
        qf = make_qf(revenue=(100, 90, 80, 75, 65))
        assert score_revenue_growth(qf) == 3

    def test_returns_2_for_growth_between_25_and_40(self):
        # 100 / 75 - 1 = 33.3%
        qf = make_qf(revenue=(100, 95, 90, 85, 75))
        assert score_revenue_growth(qf) == 2

    def test_returns_1_for_growth_between_15_and_25(self):
        # 100 / 85 - 1 = 17.6%
        qf = make_qf(revenue=(100, 97, 92, 88, 85))
        assert score_revenue_growth(qf) == 1

    def test_returns_0_for_growth_below_15pct(self):
        # 100 / 95 - 1 = 5.3%
        qf = make_qf(revenue=(100, 99, 97, 96, 95))
        assert score_revenue_growth(qf) == 0

    def test_returns_0_for_declining_revenue(self):
        qf = make_qf(revenue=(80, 85, 90, 95, 100))
        assert score_revenue_growth(qf) == 0

    def test_returns_0_for_insufficient_quarters(self):
        qf = make_qf(revenue=(100, 90, 80))  # only 3 quarters
        assert score_revenue_growth(qf) == 0

    def test_returns_0_for_missing_line_item(self):
        # qf without "Total Revenue" row
        qf = pd.DataFrame(
            {pd.Timestamp("2026-03-31"): [100]},
            index=["Gross Profit"],
        )
        assert score_revenue_growth(qf) == 0

    def test_returns_0_for_none_input(self):
        assert score_revenue_growth(None) == 0


# -----------------------------------------------------------------------------
# 2. Margin expansion (gross)
# -----------------------------------------------------------------------------

class TestScoreMarginExpansion:
    def test_returns_2_for_two_consecutive_expansions(self):
        # Margins: 0.70, 0.65, 0.60 — expanding for 2 consecutive Qs
        qf = make_qf(
            revenue=(100, 100, 100, 100),
            gross=(70, 65, 60, 55),
        )
        assert score_margin_expansion(qf) == 2

    def test_returns_1_for_single_quarter_expansion(self):
        # Margins: 0.70, 0.65, 0.65, 0.65 — only one expansion (latest)
        qf = make_qf(
            revenue=(100, 100, 100, 100),
            gross=(70, 65, 65, 65),
        )
        assert score_margin_expansion(qf) == 1

    def test_returns_0_for_flat_margins(self):
        qf = make_qf(
            revenue=(100, 100, 100, 100),
            gross=(60, 60, 60, 60),
        )
        assert score_margin_expansion(qf) == 0

    def test_returns_0_for_contracting_margins(self):
        qf = make_qf(
            revenue=(100, 100, 100, 100),
            gross=(55, 60, 65, 70),
        )
        assert score_margin_expansion(qf) == 0

    def test_returns_0_for_insufficient_quarters(self):
        qf = make_qf(revenue=(100, 100), gross=(70, 60))  # only 2 quarters
        assert score_margin_expansion(qf) == 0

    def test_returns_0_for_zero_revenue(self):
        qf = make_qf(revenue=(0, 100, 100), gross=(0, 60, 60))
        assert score_margin_expansion(qf) == 0


# -----------------------------------------------------------------------------
# 3. Profitability path
# -----------------------------------------------------------------------------

class TestScoreProfitabilityPath:
    def test_returns_2_for_positive_fcf_latest(self):
        qf = make_qf()
        qcf = make_qcf(fcf=(10, -2, -5, -10))
        assert score_profitability_path(qf, qcf) == 2

    def test_returns_1_for_narrowing_op_loss_when_fcf_negative(self):
        # FCF still negative but op_income improving 2+ Qs
        qf = make_qf(
            revenue=(100, 95, 90, 85),
            op_income=(-5, -10, -15, -20),  # losses narrowing each quarter
        )
        qcf = make_qcf(fcf=(-3, -5, -8, -12))
        assert score_profitability_path(qf, qcf) == 1

    def test_returns_0_when_fcf_negative_and_losses_widening(self):
        qf = make_qf(
            revenue=(100, 95, 90, 85),
            op_income=(-20, -15, -10, -5),  # losses widening
        )
        qcf = make_qcf(fcf=(-15, -10, -5, -2))
        assert score_profitability_path(qf, qcf) == 0

    def test_returns_0_for_missing_fcf_and_missing_op_income(self):
        empty = pd.DataFrame()
        assert score_profitability_path(empty, empty) == 0

    def test_returns_0_for_none_inputs(self):
        assert score_profitability_path(None, None) == 0


# -----------------------------------------------------------------------------
# 4. PE compression
# -----------------------------------------------------------------------------

class TestScorePeCompression:
    def test_returns_2_for_ratio_below_0_7(self):
        info = {"forwardPE": 15, "trailingPE": 25}  # 15/25 = 0.60
        assert score_pe_compression(info) == 2

    def test_returns_1_for_ratio_between_0_7_and_0_85(self):
        info = {"forwardPE": 20, "trailingPE": 25}  # 20/25 = 0.80
        assert score_pe_compression(info) == 1

    def test_returns_0_for_ratio_above_0_85(self):
        info = {"forwardPE": 23, "trailingPE": 25}  # 23/25 = 0.92
        assert score_pe_compression(info) == 0

    def test_returns_0_when_forward_pe_missing(self):
        assert score_pe_compression({"trailingPE": 25}) == 0

    def test_returns_0_when_trailing_pe_missing(self):
        assert score_pe_compression({"forwardPE": 15}) == 0

    def test_returns_0_when_trailing_pe_zero_or_negative(self):
        # Unprofitable companies have negative or null trailing PE
        assert score_pe_compression({"forwardPE": 15, "trailingPE": 0}) == 0
        assert score_pe_compression({"forwardPE": 15, "trailingPE": -5}) == 0

    def test_returns_0_when_forward_pe_negative(self):
        assert score_pe_compression({"forwardPE": -5, "trailingPE": 25}) == 0

    def test_returns_0_for_none_input(self):
        assert score_pe_compression(None) == 0


# -----------------------------------------------------------------------------
# 5. Earnings beat
# -----------------------------------------------------------------------------

class TestScoreEarningsBeat:
    def test_returns_1_for_positive_quarterly_growth(self):
        assert score_earnings_beat({"earningsQuarterlyGrowth": 0.25}) == 1

    def test_returns_0_for_negative_quarterly_growth(self):
        assert score_earnings_beat({"earningsQuarterlyGrowth": -0.1}) == 0

    def test_returns_0_for_zero_quarterly_growth(self):
        assert score_earnings_beat({"earningsQuarterlyGrowth": 0}) == 0

    def test_returns_0_when_missing(self):
        assert score_earnings_beat({}) == 0
        assert score_earnings_beat({"earningsQuarterlyGrowth": None}) == 0

    def test_returns_0_for_none_input(self):
        assert score_earnings_beat(None) == 0


# -----------------------------------------------------------------------------
# Aggregate
# -----------------------------------------------------------------------------

class TestGrowthInflectionScore:
    def test_returns_all_components_and_total(self):
        qf = make_qf()
        qcf = make_qcf()
        info = {"forwardPE": 15, "trailingPE": 25, "earningsQuarterlyGrowth": 0.5}
        result = growth_inflection_score(qf, qcf, info)
        assert set(result.keys()) == {
            "revenue_growth", "margin_expansion", "profitability_path",
            "pe_compression", "earnings_beat", "total",
        }
        non_total = {k: v for k, v in result.items() if k != "total"}
        assert result["total"] == sum(non_total.values())
        assert 0 <= result["total"] <= 10

    def test_strong_inflection_scores_high(self):
        # Revenue: 100→65 = 54% YoY (3 pts)
        # Margins: 70%, 65%, 60% expanding (2 pts)
        # FCF positive (2 pts)
        # PE: 15/25 = 0.6 (2 pts)
        # Earnings growth positive (1 pt) → 10 total
        qf = make_qf(
            revenue=(100, 90, 80, 75, 65),
            gross=(70, 58.5, 48, 42, 35),  # margins: 70, 65, 60, 56, 54
        )
        qcf = make_qcf(fcf=(10, 5, 2, -1, -3))
        info = {"forwardPE": 15, "trailingPE": 25, "earningsQuarterlyGrowth": 0.5}
        result = growth_inflection_score(qf, qcf, info)
        assert result["total"] >= 8

    def test_distressed_company_scores_zero(self):
        # Declining revenue, contracting margins, negative FCF widening,
        # PE expanding, earnings dropping
        qf = make_qf(
            revenue=(60, 70, 80, 90, 100),
            gross=(30, 38, 45, 52, 60),  # margins: 50, 54, 56, 58, 60 - contracting
            op_income=(-20, -15, -10, -5, 0),
        )
        qcf = make_qcf(fcf=(-15, -10, -5, -2, 1))
        info = {"forwardPE": 28, "trailingPE": 25, "earningsQuarterlyGrowth": -0.4}
        result = growth_inflection_score(qf, qcf, info)
        assert result["total"] == 0

    def test_handles_all_missing_data(self):
        result = growth_inflection_score(None, None, None)
        assert result["total"] == 0
