from lighthouse.universe import (
    build_universe,
    is_common_stock,
    parse_nasdaq_listed,
    parse_other_listed,
    to_yahoo_symbol,
)


NASDAQ_FIXTURE = """\
Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N
ZZZT|Test Issue Co - Common Stock|Q|Y|N|100|N|N
QQQ|Invesco QQQ Trust - ETF|G|N|N|100|Y|N
ABCDW|Some SPAC Warrant|S|N|N|100|N|N
ABCDU|Some SPAC Unit|S|N|N|100|N|N
ABCDR|Some Rights|S|N|N|100|N|N
GOOGL|Alphabet Inc. - Class A Common Stock|Q|N|N|100|N|N
File Creation Time: 0513202618:00|||||||
"""

OTHER_FIXTURE = """\
ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
A|Agilent Technologies, Inc. Common Stock|N|A|N|100|N|A
BRK.A|Berkshire Hathaway Inc. Class A|N|BRK A|N|100|N|BRK-A
AA$B|Alcoa Inc. Depositary Shares|N|AA p B|N|100|N|AA-B
SPY|SPDR S&P 500|P|SPY|Y|100|N|SPY
ZTEST|Test Common Stock|N|ZTEST|N|100|Y|ZTEST
File Creation Time: 0513202618:00|||||||
"""


class TestParseNasdaqListed:
    def test_extracts_records_with_expected_fields(self):
        records = parse_nasdaq_listed(NASDAQ_FIXTURE)
        symbols = [r["symbol"] for r in records]
        assert "AAPL" in symbols
        assert "GOOGL" in symbols

    def test_skips_header_row(self):
        records = parse_nasdaq_listed(NASDAQ_FIXTURE)
        assert all(r["symbol"] != "Symbol" for r in records)

    def test_skips_file_creation_time_footer(self):
        records = parse_nasdaq_listed(NASDAQ_FIXTURE)
        assert not any("File Creation Time" in r["symbol"] for r in records)

    def test_captures_etf_flag(self):
        records = parse_nasdaq_listed(NASDAQ_FIXTURE)
        qqq = next(r for r in records if r["symbol"] == "QQQ")
        assert qqq["etf"] == "Y"

    def test_captures_test_issue_flag(self):
        records = parse_nasdaq_listed(NASDAQ_FIXTURE)
        zzzt = next(r for r in records if r["symbol"] == "ZZZT")
        assert zzzt["test_issue"] == "Y"

    def test_handles_empty_input(self):
        assert parse_nasdaq_listed("") == []


class TestParseOtherListed:
    def test_extracts_records(self):
        records = parse_other_listed(OTHER_FIXTURE)
        symbols = [r["symbol"] for r in records]
        assert "A" in symbols
        assert "BRK.A" in symbols

    def test_captures_etf_flag(self):
        records = parse_other_listed(OTHER_FIXTURE)
        spy = next(r for r in records if r["symbol"] == "SPY")
        assert spy["etf"] == "Y"

    def test_captures_test_issue_flag(self):
        records = parse_other_listed(OTHER_FIXTURE)
        ztest = next(r for r in records if r["symbol"] == "ZTEST")
        assert ztest["test_issue"] == "Y"

    def test_skips_footer(self):
        records = parse_other_listed(OTHER_FIXTURE)
        assert not any("File Creation Time" in r["symbol"] for r in records)


class TestIsCommonStock:
    def _rec(self, **overrides):
        base = {"symbol": "ABCD", "security_name": "ABCD Inc. Common Stock", "etf": "N", "test_issue": "N"}
        base.update(overrides)
        return base

    def test_keeps_plain_common_stock(self):
        assert is_common_stock(self._rec()) is True

    def test_excludes_etf(self):
        assert is_common_stock(self._rec(etf="Y")) is False

    def test_excludes_test_issue(self):
        assert is_common_stock(self._rec(test_issue="Y")) is False

    def test_excludes_warrant_suffix_w(self):
        assert is_common_stock(self._rec(symbol="ABCDW")) is False

    def test_excludes_warrant_suffix_ws(self):
        assert is_common_stock(self._rec(symbol="ABCDWS")) is False

    def test_excludes_unit_suffix(self):
        assert is_common_stock(self._rec(symbol="ABCDU")) is False

    def test_excludes_rights_suffix(self):
        assert is_common_stock(self._rec(symbol="ABCDR")) is False

    def test_excludes_preferred_dollar_delimiter(self):
        # NYSE preferred shares: "AA$B"
        assert is_common_stock(self._rec(symbol="AA$B")) is False

    def test_excludes_when_name_says_warrant(self):
        assert is_common_stock(self._rec(security_name="Acme Corp - Warrant")) is False

    def test_excludes_when_name_says_unit(self):
        assert is_common_stock(self._rec(security_name="Acme Corp - Unit")) is False

    def test_excludes_when_name_says_preferred(self):
        assert is_common_stock(self._rec(security_name="Acme Corp - 6.5% Preferred")) is False

    def test_keeps_class_a_share(self):
        rec = self._rec(symbol="BRK.A", security_name="Berkshire Hathaway Class A")
        assert is_common_stock(rec) is True


class TestToYahooSymbol:
    def test_converts_dot_to_dash(self):
        # BRK.A on Nasdaq -> BRK-A on Yahoo
        assert to_yahoo_symbol("BRK.A") == "BRK-A"

    def test_leaves_plain_symbol_unchanged(self):
        assert to_yahoo_symbol("AAPL") == "AAPL"


class TestBuildUniverse:
    def test_combines_and_filters_both_sources(self):
        universe = build_universe(NASDAQ_FIXTURE, OTHER_FIXTURE)
        # Should keep: AAPL, GOOGL (Nasdaq), A, BRK-A (other)
        # Should exclude: ZZZT (test), QQQ (ETF), ABCDW/U/R (warrants/units/rights),
        #                 AA$B (preferred), SPY (ETF), ZTEST (test)
        assert "AAPL" in universe
        assert "GOOGL" in universe
        assert "A" in universe
        assert "BRK-A" in universe  # normalized
        for excluded in ["ZZZT", "QQQ", "ABCDW", "ABCDU", "ABCDR", "AA$B", "SPY", "ZTEST", "BRK.A"]:
            assert excluded not in universe

    def test_deduplicates(self):
        # Same ticker in both files should appear once
        nasdaq_with_dup = NASDAQ_FIXTURE + "DUPE|Dupe Inc - Common Stock|Q|N|N|100|N|N\n"
        other_with_dup = OTHER_FIXTURE + "DUPE|Dupe Inc Common Stock|N|DUPE|N|100|N|DUPE\n"
        universe = build_universe(nasdaq_with_dup, other_with_dup)
        assert universe.count("DUPE") == 1

    def test_returns_sorted_list(self):
        universe = build_universe(NASDAQ_FIXTURE, OTHER_FIXTURE)
        assert universe == sorted(universe)
