import plotly.graph_objects as go


_BG = "#0f1117"
_GREEN = "#22c55e"
_RED = "#ef4444"
_YELLOW = "#facc15"
_ORANGE = "#f97316"
_TEAL = "#2dd4bf"
_NAVY = "#1e3a5f"
_TEXT = "#e2e8f0"


def build_sparkline(closes: list, week_change: float) -> str:
    """
    Return an HTML div containing a minimal 5-point sparkline.
    Color is green if week_change >= 0, red otherwise.
    """
    color = _GREEN if week_change >= 0 else _RED
    fig = go.Figure(go.Scatter(
        x=list(range(len(closes))),
        y=closes,
        mode="lines",
        line={"color": color, "width": 2},
        hoverinfo="skip",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        width=200,
        height=60,
        xaxis={"visible": False, "fixedrange": True},
        yaxis={"visible": False, "fixedrange": True},
        showlegend=False,
    )
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})


def build_gauge(pct: float) -> str:
    """
    Return an HTML div with a circular gauge showing pct (0.0–1.0).
    Arc color: green >60%, yellow 40–60%, red <40%.
    Label and count are rendered by the caller in HTML.
    """
    value = round(pct * 100, 1)
    if pct > 0.60:
        bar_color = _GREEN
    elif pct >= 0.40:
        bar_color = _YELLOW
    else:
        bar_color = _RED

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix": "%", "font": {"color": bar_color, "size": 32}},
        gauge={
            "axis": {"range": [0, 100], "visible": False},
            "bar":  {"color": bar_color, "thickness": 0.25},
            "bgcolor": "#263347",
            "borderwidth": 0,
            "threshold": {"line": {"color": "white", "width": 0}, "thickness": 0, "value": 0},
        },
        domain={"x": [0, 1], "y": [0, 1]},
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 16, "r": 16, "t": 16, "b": 8},
        width=200,
        height=160,
        font={"color": _TEXT},
    )
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})


def build_breadth_trend(series: list) -> str:
    """
    Return a full-width Plotly HTML div for the historical breadth trend.
    series: list of dicts with keys date, pct_positive_today, pct_above_10sma,
            pct_above_20sma, pct_above_200sma. Values are 0.0–1.0 decimals.
    Time range buttons: 1W, 1M, 3M, 6M, YTD (via Plotly relayout).
    """
    if not series:
        return "<p style='color:#94a3b8'>No breadth data available.</p>"

    dates  = [row["date"] for row in series]
    day_of = [round(row["pct_positive_today"] * 100, 1) for row in series]
    sma10  = [round(row["pct_above_10sma"]    * 100, 1) for row in series]
    sma20  = [round(row["pct_above_20sma"]    * 100, 1) for row in series]
    sma200 = [round(row["pct_above_200sma"]   * 100, 1) for row in series]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=sma200, name="200-Day Breadth", line={"color": _NAVY, "width": 2}))
    fig.add_trace(go.Scatter(x=dates, y=sma20,  name="20-Day",          line={"color": _ORANGE, "width": 2}))
    fig.add_trace(go.Scatter(x=dates, y=sma10,  name="10-Day",          line={"color": _GREEN, "width": 2}))
    fig.add_trace(go.Scatter(x=dates, y=day_of, name="Day of",          line={"color": _YELLOW, "width": 1, "dash": "dot"}))

    # Horizontal reference lines
    fig.add_hline(y=80, line={"color": _TEAL, "width": 1, "dash": "dash"}, annotation_text="80%", annotation_position="right")
    fig.add_hline(y=25, line={"color": _RED,  "width": 1, "dash": "dash"}, annotation_text="25%", annotation_position="right")

    # Time range buttons using Plotly relayout
    fig.update_layout(
        paper_bgcolor=_BG,
        plot_bgcolor="#111827",
        font={"color": _TEXT},
        margin={"l": 50, "r": 60, "t": 40, "b": 80},
        height=380,
        xaxis={
            "gridcolor": "#1e293b",
            "tickformat": "%b %d",
            "rangeselector": {
                "buttons": [
                    {"count": 7,  "label": "1W", "step": "day",   "stepmode": "backward"},
                    {"count": 1,  "label": "1M", "step": "month", "stepmode": "backward"},
                    {"count": 3,  "label": "3M", "step": "month", "stepmode": "backward"},
                    {"count": 6,  "label": "6M", "step": "month", "stepmode": "backward"},
                    {"step": "year", "stepmode": "todate", "label": "YTD"},
                ],
                "activecolor": "#3b82f6",
                "bgcolor": "#1e293b",
                "bordercolor": "#334155",
                "font": {"color": _TEXT},
            },
            "type": "date",
        },
        yaxis={
            "range": [0, 100],
            "gridcolor": "#1e293b",
            "ticksuffix": "%",
        },
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.18,
            "xanchor": "center",
            "x": 0.5,
        },
        hovermode="x unified",
    )
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})
