import logging
import pandas as pd
from config import (
    PRICE_MIN, PRICE_MAX, AVG_VOLUME_MIN, FLOAT_MIN, FLOAT_MAX,
    ATR_MIN_DOLLAR, ATR_MIN_PCT, GAP_MIN_PCT, RVOL_MIN,
    EMA_FAST_GAP_THRESHOLD, EMA_FAST_ATR_PCT_THRESHOLD,
)


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply the full EOD scan filter pipeline.

    Expected input columns: ticker, close, avg_volume_20d, float_shares,
                            atr_14, gap_pct, rvol
    Returns a filtered copy with added columns: atr_pct, ema (9 or 21).
    """
    df = df.copy()

    # Step 1: Price
    df = df[(df["close"] >= PRICE_MIN) & (df["close"] <= PRICE_MAX)]

    # Step 2: Average volume
    df = df[df["avg_volume_20d"] >= AVG_VOLUME_MIN]

    # Step 3: Float — best-effort, skip (do not exclude) when None
    has_float = df["float_shares"].notna()
    excluded = df[has_float & (
        (df["float_shares"] < FLOAT_MIN) | (df["float_shares"] > FLOAT_MAX)
    )]
    if len(excluded) > 0:
        logging.warning("Float filter excluded: %s", excluded["ticker"].tolist())
    df = df[~df.index.isin(excluded.index)]

    # Step 4: ATR (dollar and percent)
    df["atr_pct"] = df["atr_14"] / df["close"]
    df = df[(df["atr_14"] >= ATR_MIN_DOLLAR) & (df["atr_pct"] >= ATR_MIN_PCT)]

    # Step 5: Gap
    df = df[df["gap_pct"] >= GAP_MIN_PCT]

    # Step 6: RVOL
    df = df[df["rvol"] >= RVOL_MIN]

    # EMA column: 9 for high-momentum stocks, 21 otherwise
    df["ema"] = df.apply(
        lambda row: 9
        if (row["gap_pct"] >= EMA_FAST_GAP_THRESHOLD
            or row["atr_pct"] >= EMA_FAST_ATR_PCT_THRESHOLD)
        else 21,
        axis=1,
    )

    return df.reset_index(drop=True)
