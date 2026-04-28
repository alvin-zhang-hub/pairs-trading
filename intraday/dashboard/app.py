import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, redirect, url_for

from dashboard.data import fetch_index_data, get_breadth_series
from dashboard.regime import classify_regime
from dashboard.charts import build_sparkline, build_gauge, build_breadth_trend

app = Flask(__name__)

_ET = ZoneInfo("America/New_York")


def _market_status() -> tuple[str, str]:
    """Return (label, dot_color) based on current ET time."""
    now = datetime.now(_ET)
    is_weekday = now.weekday() < 5
    is_open_hours = 9 * 60 + 30 <= now.hour * 60 + now.minute < 16 * 60
    if is_weekday and is_open_hours:
        return "Markets Open", "#22c55e"
    return "Markets Closed", "#94a3b8"


def _render_dashboard(index_data: dict, breadth_series: list, error: str | None = None) -> str:
    regime = classify_regime(
        qqq_vs_spy=index_data.get("qqq_vs_spy", 0.0),
        iwm_vs_spy=index_data.get("iwm_vs_spy", 0.0),
        spy_week_return=index_data.get("SPY", {}).get("week_pct", 0.0),
    )

    # Build sparklines
    sparklines = {}
    for ticker in ["SPY", "QQQ", "IWM"]:
        d = index_data.get(ticker, {})
        sparklines[ticker] = build_sparkline(d.get("sparkline", []), d.get("week_pct", 0.0))

    # Build gauges — use last series entry for today's values
    today_breadth = breadth_series[-1] if breadth_series else {}
    gauge_day  = build_gauge(today_breadth.get("pct_positive_today", 0.0), "DAY-OF BREADTH")
    gauge_10   = build_gauge(today_breadth.get("pct_above_10sma", 0.0),    "10-DAY SMA")
    gauge_20   = build_gauge(today_breadth.get("pct_above_20sma", 0.0),    "20-DAY SMA")
    gauge_200  = build_gauge(today_breadth.get("pct_above_200sma", 0.0),   "200-DAY SMA")

    # Stock counts (approximate from pct × 500)
    n = 500
    count_day  = round(today_breadth.get("pct_positive_today", 0.0) * n)
    count_10   = round(today_breadth.get("pct_above_10sma", 0.0) * n)
    count_20   = round(today_breadth.get("pct_above_20sma", 0.0) * n)
    count_200  = round(today_breadth.get("pct_above_200sma", 0.0) * n)

    trend_html = build_breadth_trend(breadth_series)

    market_label, dot_color = _market_status()

    def fmt_pct(v):
        sign = "+" if v >= 0 else ""
        color = "#22c55e" if v >= 0 else "#ef4444"
        return f'<span style="color:{color}">{sign}{v*100:.2f}%</span>'

    def price_card(ticker, label):
        d = index_data.get(ticker, {})
        sp = sparklines[ticker]
        week_vs = ""
        if ticker in ("QQQ", "IWM"):
            delta_key = "qqq_vs_spy" if ticker == "QQQ" else "iwm_vs_spy"
            delta = index_data.get(delta_key, 0.0)
            vs_color = "#22c55e" if delta >= 0 else "#ef4444"
            vs_label = "Outperforming" if delta >= 0 else "Underperforming"
            week_vs = f'<div style="font-size:11px;color:{vs_color};margin-top:4px">1-Week vs S&amp;P 500 &nbsp; {vs_label} ({delta*100:+.1f}%)</div>'
        return f"""
        <div style="background:#1e293b;border-radius:8px;padding:20px;flex:1;min-width:260px">
          <div style="font-size:22px;font-weight:700;color:#e2e8f0">{ticker}</div>
          <div style="font-size:12px;color:#94a3b8;margin-bottom:8px">{label}</div>
          <div style="font-size:36px;font-weight:700;color:#f8fafc">${d.get('price', 0):,.2f}</div>
          <div style="display:flex;gap:20px;margin:8px 0;font-size:12px">
            <div><span style="color:#64748b">DAY</span> {fmt_pct(d.get('day_pct',0))}</div>
            <div><span style="color:#64748b">WEEK</span> {fmt_pct(d.get('week_pct',0))}</div>
            <div><span style="color:#64748b">MONTH</span> {fmt_pct(d.get('month_pct',0))}</div>
          </div>
          {sp}
          {week_vs}
        </div>"""

    error_banner = ""
    if error:
        error_banner = f'<div style="background:#7f1d1d;color:#fca5a5;padding:12px 20px;border-radius:6px;margin-bottom:16px">⚠ {error}</div>'

    bullets_html = "".join(
        f'<div style="margin:8px 0;font-size:16px;color:#cbd5e1">▪ {b}</div>'
        for b in regime["bullets"]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Market Health Dashboard</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f1117; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 24px; }}
    h2 {{ font-size: 22px; font-weight: 700; }}
    .section-title {{ font-size: 18px; font-weight: 600; color: #e2e8f0; margin-bottom: 4px; }}
    .section-sub {{ font-size: 12px; color: #64748b; margin-bottom: 16px; }}
    .row {{ display: flex; gap: 16px; flex-wrap: wrap; }}
    .gauge-row {{ display: flex; gap: 8px; flex-wrap: wrap; justify-content: space-around; }}
    .count-row {{ display: flex; gap: 8px; flex-wrap: wrap; justify-content: space-around; text-align: center; font-size: 12px; color: #64748b; margin-top: -8px; margin-bottom: 16px; }}
    .count-cell {{ flex: 1; min-width: 120px; }}
    .count-val {{ font-size: 22px; font-weight: 700; color: #facc15; }}
  </style>
</head>
<body>
  <!-- Header -->
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;border-bottom:1px solid #1e293b;padding-bottom:16px">
    <h2>Market Health Dashboard</h2>
    <div style="display:flex;align-items:center;gap:16px">
      <span style="font-size:13px;color:#94a3b8">
        <span style="color:{dot_color}">●</span> {market_label}
      </span>
      <form method="POST" action="/refresh" style="margin:0">
        <button type="submit" style="background:#3b82f6;color:white;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:14px">↻ Refresh</button>
      </form>
    </div>
  </div>

  {error_banner}

  <!-- Section 1: Index Cards -->
  <div class="section-title">Market Indices</div>
  <div class="section-sub">Real-time market regime analysis</div>
  <div class="row" style="margin-bottom:32px">
    {price_card("SPY", "S&P 500")}
    {price_card("QQQ", "NASDAQ 100")}
    {price_card("IWM", "RUSSELL 2000")}
  </div>

  <!-- Section 2: Regime Box -->
  <div style="text-align:center;margin-bottom:32px;padding:32px;background:#111827;border-radius:8px">
    <div style="font-size:11px;color:#64748b;letter-spacing:2px;margin-bottom:12px">THIS WEEK'S MARKET HEALTH CHECK</div>
    <div style="font-size:42px;font-weight:700;color:{regime['color']};margin-bottom:20px">{regime['label']}</div>
    {bullets_html}
    <hr style="border:none;border-top:1px solid #1e293b;margin:20px auto;max-width:400px">
    <div style="font-size:13px;color:#64748b">Translation: {regime['translation']}</div>
  </div>

  <!-- Section 3: Breadth Gauges -->
  <div class="section-title">S&amp;P 500 Breadth Indicators</div>
  <div class="section-sub">Market participation metrics</div>
  <div class="gauge-row">
    <div>{gauge_day}</div>
    <div>{gauge_10}</div>
    <div>{gauge_20}</div>
    <div>{gauge_200}</div>
  </div>
  <div class="count-row">
    <div class="count-cell"><div class="count-val">{count_day}</div><div>STOCKS POSITIVE TODAY</div></div>
    <div class="count-cell"><div class="count-val">{count_10}</div><div>ABOVE 10-DAY SMA</div></div>
    <div class="count-cell"><div class="count-val">{count_20}</div><div>ABOVE 20-DAY SMA</div></div>
    <div class="count-cell"><div class="count-val">{count_200}</div><div>ABOVE 200-DAY SMA</div></div>
  </div>

  <!-- Section 4: Historical Breadth Trend -->
  <div class="section-title">Historical Breadth Trends</div>
  <div class="section-sub">Breadth percentages over time — extremes marked at 25% and 80%</div>
  <div style="background:#111827;border-radius:8px;padding:8px">
    {trend_html}
  </div>

  <div style="text-align:center;font-size:11px;color:#334155;margin-top:24px">
    Last session: {today_breadth.get('date', '—')} | {market_label}
  </div>
</body>
</html>"""


@app.route("/")
def index():
    error = None
    try:
        index_data = fetch_index_data()
    except Exception:
        traceback.print_exc()
        error = "Failed to fetch index prices. Showing cached breadth data only."
        index_data = {"SPY": {}, "QQQ": {}, "IWM": {}, "qqq_vs_spy": 0.0, "iwm_vs_spy": 0.0}

    # NOTE: on first run or cache miss, get_breadth_series() fetches ~500 tickers
    # and blocks for 1-3 minutes. This is expected behaviour for a local dashboard.
    breadth_series = get_breadth_series()
    return _render_dashboard(index_data, breadth_series, error=error)


@app.route("/refresh", methods=["POST"])
def refresh():
    return redirect(url_for("index"))
