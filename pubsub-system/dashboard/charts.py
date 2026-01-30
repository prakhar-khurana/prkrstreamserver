"""
Chart Helpers for Pub/Sub Observability Dashboard.

This module provides helper functions for creating Plotly charts
used in the Streamlit dashboard.
"""

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import List, Dict, Any, Optional


# Color scheme for consistent styling
COLORS = {
    "green": "#00C851",
    "yellow": "#ffbb33", 
    "red": "#ff4444",
    "blue": "#33b5e5",
    "purple": "#aa66cc",
    "orange": "#ff8800",
    "grey": "#666666",
    "dark_bg": "#0e1117",
    "card_bg": "#1e2130"
}


def get_status_color(value: float, warning_threshold: float, critical_threshold: float) -> str:
    """
    Get color based on value and thresholds.
    
    Args:
        value: Current value
        warning_threshold: Value above which status is warning (yellow)
        critical_threshold: Value above which status is critical (red)
    
    Returns:
        Color hex string (green, yellow, or red)
    """
    if value >= critical_threshold:
        return COLORS["red"]
    elif value >= warning_threshold:
        return COLORS["yellow"]
    return COLORS["green"]


def get_queue_saturation_color(queue_depth: int, queue_max_size: int) -> str:
    """
    Get color for queue saturation indicator.
    
    Thresholds:
    - Green: < 25% full
    - Yellow: 25-75% full
    - Red: > 75% full
    """
    if queue_max_size == 0:
        return COLORS["grey"]
    
    saturation = queue_depth / queue_max_size
    if saturation >= 0.75:
        return COLORS["red"]
    elif saturation >= 0.25:
        return COLORS["yellow"]
    return COLORS["green"]


def create_time_series_chart(
    df: pd.DataFrame,
    x_col: str,
    y_cols: List[str],
    title: str,
    y_axis_title: str = "Value",
    colors: Optional[List[str]] = None
) -> go.Figure:
    """
    Create a time series line chart.
    
    Args:
        df: DataFrame with time series data
        x_col: Column name for x-axis (typically timestamp)
        y_cols: List of column names to plot
        title: Chart title
        y_axis_title: Y-axis label
        colors: Optional list of colors for each line
    
    Returns:
        Plotly Figure object
    """
    if colors is None:
        colors = [COLORS["blue"], COLORS["green"], COLORS["orange"], COLORS["purple"]]
    
    fig = go.Figure()
    
    for i, col in enumerate(y_cols):
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df[x_col],
                y=df[col],
                mode="lines",
                name=col.replace("_", " ").title(),
                line=dict(color=colors[i % len(colors)], width=2)
            ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title=y_axis_title,
        template="plotly_dark",
        height=300,
        margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig


def create_bar_chart(
    labels: List[str],
    values: List[float],
    title: str,
    color: str = None,
    y_axis_title: str = "Count"
) -> go.Figure:
    """
    Create a simple bar chart.
    
    Args:
        labels: Bar labels
        values: Bar values
        title: Chart title
        color: Bar color (uses blue if not specified)
        y_axis_title: Y-axis label
    
    Returns:
        Plotly Figure object
    """
    if color is None:
        color = COLORS["blue"]
    
    fig = go.Figure(data=[
        go.Bar(x=labels, y=values, marker_color=color)
    ])
    
    fig.update_layout(
        title=title,
        xaxis_title="Topic",
        yaxis_title=y_axis_title,
        template="plotly_dark",
        height=300,
        margin=dict(l=40, r=40, t=40, b=40)
    )
    
    return fig


def create_gauge_chart(
    value: float,
    max_value: float,
    title: str,
    unit: str = ""
) -> go.Figure:
    """
    Create a gauge/dial chart for saturation indicators.
    
    Args:
        value: Current value
        max_value: Maximum value for gauge
        title: Chart title
        unit: Unit label (e.g., "%", "msg/s")
    
    Returns:
        Plotly Figure object
    """
    percentage = (value / max_value * 100) if max_value > 0 else 0
    color = get_status_color(percentage, 50, 80)
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title},
        number={"suffix": unit},
        gauge={
            "axis": {"range": [0, max_value]},
            "bar": {"color": color},
            "bgcolor": COLORS["dark_bg"],
            "bordercolor": COLORS["grey"],
            "steps": [
                {"range": [0, max_value * 0.5], "color": "#1a3a1a"},
                {"range": [max_value * 0.5, max_value * 0.8], "color": "#3a3a1a"},
                {"range": [max_value * 0.8, max_value], "color": "#3a1a1a"}
            ],
            "threshold": {
                "line": {"color": "white", "width": 2},
                "thickness": 0.75,
                "value": value
            }
        }
    ))
    
    fig.update_layout(
        template="plotly_dark",
        height=200,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    return fig


def create_latency_histogram(
    latencies: List[float],
    title: str = "Latency Distribution"
) -> go.Figure:
    """
    Create a histogram for latency distribution.
    
    Args:
        latencies: List of latency values in ms
        title: Chart title
    
    Returns:
        Plotly Figure object
    """
    if not latencies:
        latencies = [0]
    
    fig = go.Figure(data=[
        go.Histogram(
            x=latencies,
            nbinsx=30,
            marker_color=COLORS["blue"],
            opacity=0.75
        )
    ])
    
    fig.update_layout(
        title=title,
        xaxis_title="Latency (ms)",
        yaxis_title="Frequency",
        template="plotly_dark",
        height=300,
        margin=dict(l=40, r=40, t=40, b=40)
    )
    
    return fig


def create_comparison_bar_chart(
    topics: List[str],
    published: List[int],
    delivered: List[int],
    dropped: List[int]
) -> go.Figure:
    """
    Create a grouped bar chart comparing published/delivered/dropped.
    
    Args:
        topics: List of topic names
        published: Published counts per topic
        delivered: Delivered counts per topic
        dropped: Dropped counts per topic
    
    Returns:
        Plotly Figure object
    """
    fig = go.Figure(data=[
        go.Bar(name="Published", x=topics, y=published, marker_color=COLORS["blue"]),
        go.Bar(name="Delivered", x=topics, y=delivered, marker_color=COLORS["green"]),
        go.Bar(name="Dropped", x=topics, y=dropped, marker_color=COLORS["red"])
    ])
    
    fig.update_layout(
        title="Message Counts by Topic",
        xaxis_title="Topic",
        yaxis_title="Count",
        barmode="group",
        template="plotly_dark",
        height=350,
        margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig


def create_multi_line_chart(
    df: pd.DataFrame,
    x_col: str,
    lines: Dict[str, str],
    title: str,
    y_axis_title: str = "ms"
) -> go.Figure:
    """
    Create a multi-line chart with custom labels.
    
    Args:
        df: DataFrame with data
        x_col: X-axis column
        lines: Dict mapping column names to display labels
        title: Chart title
        y_axis_title: Y-axis unit/label
    
    Returns:
        Plotly Figure object
    """
    colors_list = [COLORS["blue"], COLORS["yellow"], COLORS["red"], COLORS["purple"]]
    
    fig = go.Figure()
    
    for i, (col, label) in enumerate(lines.items()):
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df[x_col],
                y=df[col],
                mode="lines",
                name=label,
                line=dict(color=colors_list[i % len(colors_list)], width=2)
            ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title=y_axis_title,
        template="plotly_dark",
        height=300,
        margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig
