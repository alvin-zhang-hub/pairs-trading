import pandas as pd
import pytest

from lighthouse.narrative import (
    enrich_dataframe,
    load_themes,
    match_themes,
    truncate_summary,
)


# -----------------------------------------------------------------------------
# Theme loading
# -----------------------------------------------------------------------------

class TestLoadThemes:
    def test_returns_empty_dict_when_dir_missing(self, tmp_path):
        assert load_themes(str(tmp_path / "nonexistent")) == {}

    def test_returns_empty_dict_when_no_txt_files(self, tmp_path):
        (tmp_path / "readme.md").write_text("not a theme")
        assert load_themes(str(tmp_path)) == {}

    def test_loads_single_theme_file(self, tmp_path):
        (tmp_path / "ai-infra.txt").write_text("NVDA\nAMD\nTSM\n")
        themes = load_themes(str(tmp_path))
        assert themes == {"ai-infra": {"NVDA", "AMD", "TSM"}}

    def test_loads_multiple_theme_files(self, tmp_path):
        (tmp_path / "nuclear.txt").write_text("BWXT\nCCJ\n")
        (tmp_path / "reshoring.txt").write_text("CAT\nGE\n")
        themes = load_themes(str(tmp_path))
        assert themes == {
            "nuclear": {"BWXT", "CCJ"},
            "reshoring": {"CAT", "GE"},
        }

    def test_strips_whitespace_and_skips_blank_lines(self, tmp_path):
        (tmp_path / "x.txt").write_text("  NVDA  \n\nAMD\n   \n")
        themes = load_themes(str(tmp_path))
        assert themes == {"x": {"NVDA", "AMD"}}

    def test_skips_comment_lines(self, tmp_path):
        # # at start of line = comment; useful for annotating theme lists
        (tmp_path / "x.txt").write_text("# AI infrastructure\nNVDA\n# big movers\nAMD\n")
        themes = load_themes(str(tmp_path))
        assert themes == {"x": {"NVDA", "AMD"}}

    def test_uppercases_tickers(self, tmp_path):
        (tmp_path / "x.txt").write_text("nvda\nAmd\n")
        themes = load_themes(str(tmp_path))
        assert themes == {"x": {"NVDA", "AMD"}}


# -----------------------------------------------------------------------------
# Theme matching
# -----------------------------------------------------------------------------

class TestMatchThemes:
    def test_returns_empty_list_for_unmatched_ticker(self):
        themes = {"ai-infra": {"NVDA"}, "nuclear": {"BWXT"}}
        assert match_themes("XYZ", themes) == []

    def test_returns_single_theme_match(self):
        themes = {"ai-infra": {"NVDA"}}
        assert match_themes("NVDA", themes) == ["ai-infra"]

    def test_returns_multiple_themes_when_in_multiple(self):
        themes = {"ai-infra": {"NVDA"}, "datacenter": {"NVDA", "AMD"}}
        result = match_themes("NVDA", themes)
        assert set(result) == {"ai-infra", "datacenter"}

    def test_returns_sorted_themes(self):
        themes = {"zeta": {"X"}, "alpha": {"X"}, "mid": {"X"}}
        assert match_themes("X", themes) == ["alpha", "mid", "zeta"]

    def test_handles_empty_themes_dict(self):
        assert match_themes("NVDA", {}) == []


# -----------------------------------------------------------------------------
# Summary truncation
# -----------------------------------------------------------------------------

class TestTruncateSummary:
    def test_passes_through_short_text(self):
        assert truncate_summary("Short text.", max_chars=400) == "Short text."

    def test_truncates_long_text_with_ellipsis(self):
        text = "A" * 500
        result = truncate_summary(text, max_chars=400)
        assert len(result) <= 403  # 400 + "..."
        assert result.endswith("...")

    def test_truncates_at_word_boundary(self):
        text = "This is a long sentence that should be truncated cleanly mid-word would be bad"
        result = truncate_summary(text, max_chars=30)
        # Should not cut a word in half
        assert not result.endswith("ce...")
        assert result.endswith("...")

    def test_handles_none(self):
        assert truncate_summary(None) == ""

    def test_handles_empty_string(self):
        assert truncate_summary("") == ""


# -----------------------------------------------------------------------------
# DataFrame enrichment
# -----------------------------------------------------------------------------

class TestEnrichDataframe:
    def test_adds_themes_column(self, tmp_path):
        (tmp_path / "ai-infra.txt").write_text("NVDA\n")
        df = pd.DataFrame([
            {"ticker": "NVDA", "business_summary": "Designs GPUs."},
            {"ticker": "AAPL", "business_summary": "Makes phones."},
        ])
        out = enrich_dataframe(df, themes_dir=str(tmp_path))
        assert "themes" in out.columns
        assert out.loc[out["ticker"] == "NVDA", "themes"].iloc[0] == ["ai-infra"]
        assert out.loc[out["ticker"] == "AAPL", "themes"].iloc[0] == []

    def test_truncates_business_summary(self, tmp_path):
        long_summary = "A" * 600
        df = pd.DataFrame([{"ticker": "X", "business_summary": long_summary}])
        out = enrich_dataframe(df, themes_dir=str(tmp_path), summary_max_chars=200)
        assert len(out["business_summary"].iloc[0]) <= 203

    def test_handles_missing_business_summary(self, tmp_path):
        df = pd.DataFrame([{"ticker": "X", "business_summary": None}])
        out = enrich_dataframe(df, themes_dir=str(tmp_path))
        assert out["business_summary"].iloc[0] == ""

    def test_handles_empty_dataframe(self, tmp_path):
        df = pd.DataFrame(columns=["ticker", "business_summary"])
        out = enrich_dataframe(df, themes_dir=str(tmp_path))
        assert "themes" in out.columns
        assert len(out) == 0

    def test_does_not_mutate_input(self, tmp_path):
        df = pd.DataFrame([{"ticker": "X", "business_summary": "S"}])
        before = df.copy()
        enrich_dataframe(df, themes_dir=str(tmp_path))
        pd.testing.assert_frame_equal(df, before)
