"""HTML renderer for the Lighthouse scanner dashboard page.

The Flask app in `dashboard/app.py` calls `render_scanner_page(cache_path, filters)`
to produce the full page body. This module owns the data-shape-aware rendering
so the Flask layer stays a thin router.

Style and color palette mirror `dashboard/app.py` (Tailwind-inspired dark theme,
Work Sans font, Plotly-friendly accent colors) so the two pages feel like one
app, not bolted-together.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

# Color palette — mirrors dashboard/app.py
BG_BODY = "#0f1117"
BG_CARD = "#1e293b"
BG_HEADER = "#111827"
COLOR_TEXT = "#e2e8f0"
COLOR_MUTED = "#64748b"
COLOR_GREEN = "#22c55e"
COLOR_RED = "#ef4444"
COLOR_BLUE = "#3b82f6"
COLOR_YELLOW = "#facc15"
COLOR_PURPLE = "#a78bfa"


def _load_cache(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _format_mcap(mcap) -> str:
    if mcap is None:
        return "—"
    try:
        m = float(mcap)
    except (TypeError, ValueError):
        return "—"
    if m >= 1e9:
        return f"${m / 1e9:.2f}B"
    if m >= 1e6:
        return f"${m / 1e6:.0f}M"
    return f"${m:,.0f}"


def _format_adv(adv) -> str:
    if adv is None:
        return "—"
    try:
        a = float(adv)
    except (TypeError, ValueError):
        return "—"
    if a >= 1e9:
        return f"${a / 1e9:.2f}B"
    return f"${a / 1e6:.1f}M"


def _format_price(price) -> str:
    if price is None:
        return "—"
    try:
        return f"${float(price):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _format_signed_pct(value, label: str) -> str:
    """Render '+X.X% label' or '-X.X% label' with green/red coloring.

    Convention: a positive value (e.g. price above 30DMA) is bullish → green.
    """
    if value is None:
        return f'<span style="color:{COLOR_MUTED}">— {label}</span>'
    try:
        v = float(value)
    except (TypeError, ValueError):
        return f'<span style="color:{COLOR_MUTED}">— {label}</span>'
    sign = "+" if v >= 0 else ""
    color = COLOR_GREEN if v >= 0 else COLOR_RED
    return (
        f'<span style="color:{color};font-weight:600">{sign}{v * 100:.1f}%</span>'
        f'<span style="color:{COLOR_MUTED};margin-left:4px">{label}</span>'
    )


def _format_below_high(value, label: str) -> str:
    """Render '-X.X% from high'. Value is a positive drawdown fraction; small
    drawdown = near high = green; bigger drawdown = yellow/red."""
    if value is None:
        return f'<span style="color:{COLOR_MUTED}">— {label}</span>'
    try:
        v = float(value)
    except (TypeError, ValueError):
        return f'<span style="color:{COLOR_MUTED}">— {label}</span>'
    if v <= 0.05:
        color = COLOR_GREEN
    elif v <= 0.15:
        color = COLOR_YELLOW
    else:
        color = COLOR_RED
    return (
        f'<span style="color:{color};font-weight:600">-{v * 100:.1f}%</span>'
        f'<span style="color:{COLOR_MUTED};margin-left:4px">{label}</span>'
    )


def _format_timestamp(ts: str) -> str:
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y · %-I:%M %p UTC")
    except ValueError:
        return ts


def _apply_filters(results: list, filters: Optional[dict]) -> list:
    if not filters:
        return list(results)
    out = []
    for r in results:
        if filters.get("sector") and r.get("sector") != filters["sector"]:
            continue
        if filters.get("theme"):
            themes = r.get("themes") or []
            if filters["theme"] not in themes:
                continue
        if filters.get("stage2_only") and not r.get("stage2_flag"):
            continue
        if filters.get("new_only") and not r.get("new_today"):
            continue
        if filters.get("min_combined") is not None:
            try:
                if float(r.get("combined_score") or 0) < float(filters["min_combined"]):
                    continue
            except (TypeError, ValueError):
                continue
        out.append(r)
    return out


def _sort_results(results: list) -> list:
    return sorted(
        results,
        key=lambda r: (
            not r.get("stage2_flag", False),   # Stage 2 first
            -float(r.get("combined_score") or 0),  # then highest combined score
        ),
    )


def _unique_sectors(results: list) -> list:
    return sorted({r["sector"] for r in results if r.get("sector")})


def _unique_themes(results: list) -> list:
    themes = set()
    for r in results:
        for t in r.get("themes") or []:
            themes.add(t)
    return sorted(themes)


def _badge(text: str, color: str, bg_alpha: float = 0.15) -> str:
    bg = _rgba(color, bg_alpha)
    return (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
        f'background:{bg};color:{color};font-size:10px;font-weight:600;'
        f'letter-spacing:0.3px;white-space:nowrap;margin:0 4px 4px 0">{text}</span>'
    )


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _score_pill(label: str, score: int, max_score: int) -> str:
    pct = score / max_score if max_score else 0
    if pct >= 0.7:
        color = COLOR_GREEN
    elif pct >= 0.4:
        color = COLOR_YELLOW
    else:
        color = COLOR_MUTED
    return (
        f'<div style="display:flex;flex-direction:column;align-items:center;gap:2px">'
        f'<span style="font-size:9px;color:{COLOR_MUTED};letter-spacing:0.5px">{label}</span>'
        f'<span style="font-size:18px;font-weight:700;color:{color}">{score}<span style="font-size:11px;color:{COLOR_MUTED}">/{max_score}</span></span>'
        f'</div>'
    )


def _component_row(label: str, value: int, max_value: int) -> str:
    filled = "█" * value + "░" * (max_value - value)
    color = COLOR_GREEN if value >= max_value * 0.7 else (COLOR_YELLOW if value > 0 else COLOR_MUTED)
    return (
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'font-size:11px;color:{COLOR_TEXT};padding:2px 0">'
        f'<span style="color:{COLOR_MUTED}">{label}</span>'
        f'<span style="font-family:monospace;color:{color}">{filled} {value}/{max_value}</span>'
        f'</div>'
    )


def _build_hit_row(r: dict, index: int) -> str:
    ticker = r.get("ticker", "?")
    stage2 = r.get("stage2_flag", False)
    new_today = r.get("new_today", False)
    combined = int(r.get("combined_score") or 0)
    tech = int(r.get("score_total") or 0)
    fund = int(r.get("fund_total") or 0)
    sector = r.get("sector") or "—"
    industry = r.get("industry") or "—"
    summary = r.get("business_summary") or ""
    themes = r.get("themes") or []

    left_border = f"4px solid {COLOR_GREEN}" if new_today else f"4px solid {COLOR_BLUE if stage2 else 'transparent'}"

    stage2_badge = _badge("STAGE 2", COLOR_BLUE, 0.20) if stage2 else ""
    new_badge = _badge("NEW", COLOR_GREEN, 0.20) if new_today else ""

    theme_badges = "".join(_badge(t, COLOR_PURPLE) for t in themes) if themes else (
        f'<span style="font-size:11px;color:{COLOR_MUTED}">—</span>'
    )

    expand_id = f"expand-{index}"
    components_html = (
        f'<div style="margin-top:4px;padding:12px;background:{BG_HEADER};border-radius:6px">'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">'
        f'<div>'
        f'<div style="font-size:11px;color:{COLOR_MUTED};letter-spacing:1px;font-weight:600;margin-bottom:8px">TECHNICAL ({tech}/10)</div>'
        f'{_component_row("Trend (MA stack)",         r.get("score_trend", 0), 2)}'
        f'{_component_row("Relative strength (SPY)",  r.get("score_relative_strength", 0), 2)}'
        f'{_component_row("Volume accumulation",      r.get("score_volume_accumulation", 0), 2)}'
        f'{_component_row("Volatility contraction",   r.get("score_volatility_contraction", 0), 2)}'
        f'{_component_row("Distance from 52w high",   r.get("score_distance_from_high", 0), 2)}'
        f'</div>'
        f'<div>'
        f'<div style="font-size:11px;color:{COLOR_MUTED};letter-spacing:1px;font-weight:600;margin-bottom:8px">FUNDAMENTAL ({fund}/10)</div>'
        f'{_component_row("Revenue growth Y/Y",       r.get("fund_revenue_growth", 0), 3)}'
        f'{_component_row("Gross margin expansion",   r.get("fund_margin_expansion", 0), 2)}'
        f'{_component_row("Path to profitability",    r.get("fund_profitability_path", 0), 2)}'
        f'{_component_row("Forward PE compression",   r.get("fund_pe_compression", 0), 2)}'
        f'{_component_row("Earnings beat",            r.get("fund_earnings_beat", 0), 1)}'
        f'</div>'
        f'</div>'
        f'{f"<div style=\"margin-top:12px;font-size:12px;color:{COLOR_TEXT};line-height:1.6\">{summary}</div>" if summary else ""}'
        f'</div>'
    )

    # Data attributes drive client-side filtering (see <script> in _page_shell).
    # The themes attribute is a comma-joined string; the JS splits on ','.
    themes_attr = ",".join(themes)

    return f"""
    <details class="hit-row" data-ticker="{ticker}" data-sector="{sector}" data-themes="{themes_attr}"
             data-stage2="{'true' if stage2 else 'false'}" data-new="{'true' if new_today else 'false'}"
             style="background:{BG_CARD};border-left:{left_border};border-radius:8px;
                    margin-bottom:10px;padding:14px 18px;overflow:hidden">
      <summary style="cursor:pointer;list-style:none;display:grid;
                     grid-template-columns:120px 90px 1fr 1fr 200px 70px;gap:16px;align-items:center">
        <div>
          <div style="font-size:20px;font-weight:700;color:{COLOR_TEXT};letter-spacing:-0.3px">{ticker}</div>
          <div>{stage2_badge}{new_badge}</div>
        </div>
        <div style="display:flex;gap:6px">
          {_score_pill("COMB", combined, 20)}
        </div>
        <div>
          <div style="font-size:13px;color:{COLOR_TEXT};font-weight:500">{sector}</div>
          <div style="font-size:11px;color:{COLOR_MUTED}">{industry}</div>
        </div>
        <div style="display:flex;flex-wrap:wrap;align-content:flex-start">{theme_badges}</div>
        <div style="text-align:right;line-height:1.5">
          <div style="font-size:16px;color:{COLOR_TEXT};font-weight:600">{_format_price(r.get("price"))}</div>
          <div style="font-size:13px;color:{COLOR_TEXT};font-weight:500">{_format_mcap(r.get("mcap"))} <span style="color:{COLOR_MUTED};font-size:10px;font-weight:400">mcap</span></div>
          <div style="font-size:11px">{_format_below_high(r.get("pct_below_3yr_high"), "from 3y high")}</div>
          <div style="font-size:11px">{_format_signed_pct(r.get("pct_above_30dma"), "vs 30D MA")}</div>
          <div style="font-size:10px;color:{COLOR_MUTED};margin-top:2px">ADV {_format_adv(r.get("adv_20d_dollar"))}</div>
        </div>
        <div style="text-align:right;font-size:11px;color:{COLOR_MUTED};letter-spacing:1px">T:{tech} F:{fund}</div>
      </summary>
      {components_html}
    </details>
    """


def _render_empty(generated_at: str, filters: Optional[dict]) -> str:
    filter_msg = ""
    if filters and any(filters.values()):
        filter_msg = (
            f'<div style="margin-top:12px;color:{COLOR_MUTED};font-size:13px">'
            f'Active filters: {filters!r}. '
            f'<a href="/scanner" style="color:{COLOR_BLUE};text-decoration:none">Clear filters</a></div>'
        )
    return _page_shell(
        body_inner=(
            f'<div style="text-align:center;padding:64px 24px;background:{BG_HEADER};border-radius:10px">'
            f'<div style="font-size:48px;color:{COLOR_MUTED}">○</div>'
            f'<div style="margin-top:16px;font-size:18px;color:{COLOR_TEXT};font-weight:600">No scan results to show</div>'
            f'<div style="margin-top:8px;color:{COLOR_MUTED};font-size:13px">Run <code style="background:{BG_CARD};padding:2px 6px;border-radius:4px">python3 -m lighthouse.run_scanner</code> to generate hits.</div>'
            f'{filter_msg}'
            f'</div>'
        ),
        timestamp=generated_at,
        hit_count=0,
        new_count=0,
        sectors=[],
        themes_list=[],
        filters=filters,
    )


def _page_shell(body_inner: str, timestamp: str, hit_count: int, new_count: int,
                sectors: list, themes_list: list, filters: Optional[dict]) -> str:
    filters = filters or {}
    sector_options = "".join(
        f'<option value="{s}"{" selected" if filters.get("sector") == s else ""}>{s}</option>'
        for s in sectors
    )
    theme_options = "".join(
        f'<option value="{t}"{" selected" if filters.get("theme") == t else ""}>{t}</option>'
        for t in themes_list
    )
    stage2_checked = "checked" if filters.get("stage2_only") else ""
    new_checked = "checked" if filters.get("new_only") else ""

    stats_bar = (
        f'<div style="display:flex;gap:24px;align-items:baseline;margin-bottom:20px">'
        f'<div><span id="hit-count" style="font-size:32px;font-weight:700;color:{COLOR_TEXT}">{hit_count}</span>'
        f'<span style="font-size:13px;color:{COLOR_MUTED};margin-left:8px">hits</span></div>'
        f'<div><span id="new-count" style="font-size:20px;font-weight:600;color:{COLOR_GREEN}">{new_count}</span>'
        f'<span style="font-size:13px;color:{COLOR_MUTED};margin-left:6px">new today</span></div>'
        f'<div style="margin-left:auto;font-size:12px;color:{COLOR_MUTED}">Last scan: {_format_timestamp(timestamp)}</div>'
        f'</div>'
    )

    # Filters use onchange handlers; no server roundtrip needed. The form action
    # remains pointing to /scanner so direct URL params (e.g. ?sector=Technology)
    # still pre-filter the server-side render — useful for shareable links.
    filter_bar = f"""
    <form method="GET" action="/scanner" id="filter-form"
          onsubmit="event.preventDefault(); applyFilters();"
          style="background:{BG_CARD};padding:14px 18px;border-radius:10px;margin-bottom:20px;
                 display:flex;gap:16px;align-items:center;flex-wrap:wrap">
      <label style="font-size:12px;color:{COLOR_MUTED}">Sector:
        <select name="sector" id="filter-sector" onchange="applyFilters()"
                style="margin-left:6px;background:{BG_HEADER};color:{COLOR_TEXT};
                       border:1px solid #334155;padding:6px 10px;border-radius:6px">
          <option value="">All</option>
          {sector_options}
        </select>
      </label>
      <label style="font-size:12px;color:{COLOR_MUTED}">Theme:
        <select name="theme" id="filter-theme" onchange="applyFilters()"
                style="margin-left:6px;background:{BG_HEADER};color:{COLOR_TEXT};
                       border:1px solid #334155;padding:6px 10px;border-radius:6px">
          <option value="">All</option>
          {theme_options}
        </select>
      </label>
      <label style="font-size:12px;color:{COLOR_TEXT};display:flex;align-items:center;gap:6px">
        <input type="checkbox" name="stage2_only" id="filter-stage2" value="1" {stage2_checked}
               onchange="applyFilters()"> Stage 2 only
      </label>
      <label style="font-size:12px;color:{COLOR_TEXT};display:flex;align-items:center;gap:6px">
        <input type="checkbox" name="new_only" id="filter-new" value="1" {new_checked}
               onchange="applyFilters()"> New today only
      </label>
      <a href="#" onclick="resetFilters(); return false;"
         style="color:{COLOR_MUTED};text-decoration:none;font-size:12px">Reset</a>
    </form>
    """

    # Client-side filtering: hides/shows rows based on data-* attributes.
    # Works identically on the local Flask page and the static GH Pages export.
    filter_js = """
    <script>
    function applyFilters() {
      const sector = document.getElementById('filter-sector').value;
      const theme = document.getElementById('filter-theme').value;
      const stage2Only = document.getElementById('filter-stage2').checked;
      const newOnly = document.getElementById('filter-new').checked;
      const rows = document.querySelectorAll('details.hit-row');
      let visible = 0, newVisible = 0;
      rows.forEach(row => {
        const rSector = row.dataset.sector || '';
        const rThemes = (row.dataset.themes || '').split(',').filter(t => t.length > 0);
        const rStage2 = row.dataset.stage2 === 'true';
        const rNew = row.dataset.new === 'true';
        let show = true;
        if (sector && rSector !== sector) show = false;
        if (theme && !rThemes.includes(theme)) show = false;
        if (stage2Only && !rStage2) show = false;
        if (newOnly && !rNew) show = false;
        row.style.display = show ? '' : 'none';
        if (show) {
          visible++;
          if (rNew) newVisible++;
        }
      });
      document.getElementById('hit-count').textContent = visible;
      document.getElementById('new-count').textContent = newVisible;
    }
    function resetFilters() {
      document.getElementById('filter-sector').value = '';
      document.getElementById('filter-theme').value = '';
      document.getElementById('filter-stage2').checked = false;
      document.getElementById('filter-new').checked = false;
      applyFilters();
    }
    </script>
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Lighthouse Scanner</title>
  <link href="https://fonts.googleapis.com/css2?family=Work+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: {BG_BODY}; color: {COLOR_TEXT}; font-family: 'Work Sans', sans-serif; padding: 24px; }}
    h2 {{ font-size: 22px; font-weight: 700; letter-spacing: -0.3px; }}
    details summary::-webkit-details-marker {{ display:none; }}
    details[open] {{ border-color: {COLOR_BLUE}; }}
    a {{ color: {COLOR_BLUE}; }}
    code {{ font-family: 'SF Mono', monospace; font-size: 12px; }}
  </style>
</head>
<body>
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;
              border-bottom:1px solid {BG_CARD};padding-bottom:16px">
    <div style="display:flex;align-items:baseline;gap:20px">
      <h2>Lighthouse Scanner</h2>
    </div>
  </div>

  {stats_bar}
  {filter_bar}
  {body_inner}
  {filter_js}
</body>
</html>"""


def render_scanner_page(cache_path: str, filters: Optional[dict] = None) -> str:
    """Render the full scanner HTML page from a JSON cache. Empty/missing cache
    yields a polished empty state."""
    cache = _load_cache(cache_path)
    raw_results = cache.get("results") or []
    timestamp = cache.get("generated_at", "")

    if not raw_results:
        return _render_empty(timestamp, filters)

    filtered = _apply_filters(raw_results, filters)
    sorted_results = _sort_results(filtered)

    rows = "".join(_build_hit_row(r, i) for i, r in enumerate(sorted_results))
    if not rows:
        return _render_empty(timestamp, filters)

    new_count = sum(1 for r in sorted_results if r.get("new_today"))

    return _page_shell(
        body_inner=rows,
        timestamp=timestamp,
        hit_count=len(sorted_results),
        new_count=new_count,
        sectors=_unique_sectors(raw_results),
        themes_list=_unique_themes(raw_results),
        filters=filters,
    )
