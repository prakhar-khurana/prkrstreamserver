"""
Pub/Sub Observability Dashboard

A read-only Streamlit dashboard for visualizing Pub/Sub system metrics.

Features:
- System Overview: Active topics, subscribers, rates, uptime
- Topic Drilldown: Queue depth, batch size, message counts
- Latency Visualization: Avg/P95/P99, rolling window charts
- Backpressure Visibility: Drop counts, queue saturation

IMPORTANT: This dashboard is READ-ONLY.
- NO publishing messages
- NO subscribing clients
- NO WebSocket connections
- NO control-plane actions

Run with:
    streamlit run dashboard/app.py
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime
from typing import Dict, Any, Optional

from metrics_client import MetricsClient
from charts import (
    create_time_series_chart,
    create_bar_chart,
    create_gauge_chart,
    create_latency_histogram,
    create_comparison_bar_chart,
    create_multi_line_chart,
    get_queue_saturation_color,
    get_status_color,
    COLORS
)


# ============================================================================
# Configuration
# ============================================================================

st.set_page_config(
    page_title="Pub/Sub Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
REFRESH_INTERVAL = 1  # seconds
HISTORY_SIZE = 120    # samples (2 minutes at 1s interval)
BACKEND_URL = "http://localhost:8000"


# ============================================================================
# Session State Initialization
# ============================================================================

def init_session_state():
    """Initialize session state for storing time series data."""
    if "metrics_history" not in st.session_state:
        st.session_state.metrics_history = pd.DataFrame()
    
    if "topic_history" not in st.session_state:
        st.session_state.topic_history = {}  # topic_name -> DataFrame
    
    if "last_metrics" not in st.session_state:
        st.session_state.last_metrics = None
    
    if "client" not in st.session_state:
        st.session_state.client = MetricsClient(BACKEND_URL)
    
    if "backend_available" not in st.session_state:
        st.session_state.backend_available = False


def update_history(metrics: Dict[str, Any]):
    """Update rolling history DataFrames with new metrics."""
    now = datetime.now()
    
    # Update global metrics history
    global_data = metrics.get("global", {})
    new_row = pd.DataFrame([{
        "timestamp": now,
        "active_topics": global_data.get("active_topics", 0),
        "active_subscribers": global_data.get("active_subscribers", 0),
        "total_published": global_data.get("total_published", 0),
        "total_delivered": global_data.get("total_delivered", 0),
        "total_dropped": global_data.get("total_dropped", 0)
    }])
    
    st.session_state.metrics_history = pd.concat(
        [st.session_state.metrics_history, new_row],
        ignore_index=True
    ).tail(HISTORY_SIZE)
    
    # Update per-topic history
    topics = metrics.get("topics", {})
    for topic_name, topic_metrics in topics.items():
        if topic_name not in st.session_state.topic_history:
            st.session_state.topic_history[topic_name] = pd.DataFrame()
        
        latency = topic_metrics.get("latency_ms", {})
        topic_row = pd.DataFrame([{
            "timestamp": now,
            "queue_depth": topic_metrics.get("queue_depth", 0),
            "batch_size_avg": topic_metrics.get("batch_size_avg", 0),
            "messages_published": topic_metrics.get("messages_published", 0),
            "messages_delivered": topic_metrics.get("messages_delivered", 0),
            "messages_dropped": topic_metrics.get("messages_dropped", 0),
            "latency_avg": latency.get("avg", 0),
            "latency_p95": latency.get("p95", 0),
            "latency_p99": latency.get("p99", 0)
        }])
        
        st.session_state.topic_history[topic_name] = pd.concat(
            [st.session_state.topic_history[topic_name], topic_row],
            ignore_index=True
        ).tail(HISTORY_SIZE)


# ============================================================================
# UI Components
# ============================================================================

def render_sidebar():
    """Render the sidebar navigation."""
    st.sidebar.title("📊 Pub/Sub Dashboard")
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio(
        "Navigation",
        ["🏠 System Overview", "📈 Topic Drilldown", "⏱️ Latency", "⚠️ Backpressure"],
        label_visibility="collapsed"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.caption("🔒 Read-Only Dashboard")
    st.sidebar.caption("This dashboard does not modify backend state.")
    
    return page


def render_backend_unavailable():
    """Render error state when backend is unavailable."""
    st.error("## ⚠️ Backend Unavailable")
    st.markdown("""
    Cannot connect to the Pub/Sub backend at `{}`.
    
    **Troubleshooting:**
    1. Make sure the backend is running: `./run.sh`
    2. Check the backend URL is correct
    3. Verify there are no firewall issues
    
    The dashboard will automatically reconnect when the backend is available.
    """.format(BACKEND_URL))


def format_uptime(seconds: float) -> str:
    """Format uptime in human-readable format."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    elif seconds < 86400:
        return f"{seconds/3600:.1f}h"
    return f"{seconds/86400:.1f}d"


def format_rate(current: int, previous: int, interval: float = 1.0) -> float:
    """Calculate rate per second from cumulative counts."""
    return max(0, (current - previous) / interval)


# ============================================================================
# Pages
# ============================================================================

def page_system_overview(metrics: Dict[str, Any]):
    """
    System Overview Page
    
    Shows:
    - Active topics
    - Active subscribers  
    - Publish rate (msg/s)
    - Delivery rate (msg/s)
    - Drop rate (%)
    - Uptime
    """
    st.title("🏠 System Overview")
    st.markdown("Real-time system-wide metrics")
    
    global_data = metrics.get("global", {})
    uptime = metrics.get("uptime_seconds", 0)
    
    # Calculate rates from history
    history = st.session_state.metrics_history
    if len(history) >= 2:
        current = history.iloc[-1]
        previous = history.iloc[-2]
        publish_rate = format_rate(
            current["total_published"], 
            previous["total_published"]
        )
        delivery_rate = format_rate(
            current["total_delivered"],
            previous["total_delivered"]
        )
    else:
        publish_rate = 0
        delivery_rate = 0
    
    # Calculate drop rate
    total_published = global_data.get("total_published", 0)
    total_dropped = global_data.get("total_dropped", 0)
    drop_rate = (total_dropped / total_published * 100) if total_published > 0 else 0
    
    # Metrics row
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric(
            "Active Topics",
            global_data.get("active_topics", 0)
        )
    
    with col2:
        st.metric(
            "Active Subscribers",
            global_data.get("active_subscribers", 0)
        )
    
    with col3:
        st.metric(
            "Publish Rate",
            f"{publish_rate:.0f} msg/s"
        )
    
    with col4:
        st.metric(
            "Delivery Rate",
            f"{delivery_rate:.0f} msg/s"
        )
    
    with col5:
        drop_color = "inverse" if drop_rate > 5 else "normal"
        st.metric(
            "Drop Rate",
            f"{drop_rate:.2f}%",
            delta=None
        )
    
    with col6:
        st.metric(
            "Uptime",
            format_uptime(uptime)
        )
    
    st.markdown("---")
    
    # Time series charts
    if len(history) > 1:
        col1, col2 = st.columns(2)
        
        with col1:
            fig = create_time_series_chart(
                history,
                "timestamp",
                ["total_published", "total_delivered"],
                "Cumulative Messages Over Time",
                "Messages"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = create_time_series_chart(
                history,
                "timestamp",
                ["active_subscribers"],
                "Active Subscribers Over Time",
                "Count",
                [COLORS["purple"]]
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Collecting data... Charts will appear after a few seconds.")
    
    # Topic summary table
    st.subheader("📋 Topics Summary")
    topics = metrics.get("topics", {})
    if topics:
        table_data = []
        for name, topic_metrics in topics.items():
            latency = topic_metrics.get("latency_ms", {})
            table_data.append({
                "Topic": name,
                "Subscribers": topic_metrics.get("subscriber_count", 0),
                "Queue Depth": topic_metrics.get("queue_depth", 0),
                "Published": topic_metrics.get("messages_published", 0),
                "Delivered": topic_metrics.get("messages_delivered", 0),
                "Dropped": topic_metrics.get("messages_dropped", 0),
                "Avg Latency (ms)": latency.get("avg", 0)
            })
        
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No topics created yet.")


def page_topic_drilldown(metrics: Dict[str, Any]):
    """
    Topic Drilldown Page
    
    Shows for selected topic:
    - Queue depth over time
    - Batch size over time
    - Messages published vs delivered vs dropped
    - Live throughput
    """
    st.title("📈 Topic Drilldown")
    
    topics = metrics.get("topics", {})
    
    if not topics:
        st.info("No topics available. Create topics via the API to see metrics.")
        return
    
    # Topic selector
    topic_name = st.selectbox(
        "Select Topic",
        options=list(topics.keys()),
        key="topic_selector"
    )
    
    if not topic_name:
        return
    
    topic_metrics = topics[topic_name]
    topic_history = st.session_state.topic_history.get(topic_name, pd.DataFrame())
    
    st.markdown("---")
    
    # Current metrics
    col1, col2, col3, col4 = st.columns(4)
    
    latency = topic_metrics.get("latency_ms", {})
    
    with col1:
        queue_depth = topic_metrics.get("queue_depth", 0)
        queue_max = topic_metrics.get("queue_max_size", 10000)
        saturation = (queue_depth / queue_max * 100) if queue_max > 0 else 0
        sat_color = get_queue_saturation_color(queue_depth, queue_max)
        st.metric("Queue Depth", f"{queue_depth:,}")
        st.caption(f"Saturation: {saturation:.1f}%")
    
    with col2:
        st.metric("Batch Size Avg", f"{topic_metrics.get('batch_size_avg', 0):.1f}")
    
    with col3:
        st.metric("Subscribers", topic_metrics.get("subscriber_count", 0))
    
    with col4:
        st.metric("Avg Latency", f"{latency.get('avg', 0):.2f} ms")
    
    st.markdown("---")
    
    # Message counts comparison
    st.subheader("Message Counts")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Published", 
            f"{topic_metrics.get('messages_published', 0):,}",
            delta=None
        )
    
    with col2:
        st.metric(
            "Delivered",
            f"{topic_metrics.get('messages_delivered', 0):,}",
            delta=None
        )
    
    with col3:
        dropped = topic_metrics.get("messages_dropped", 0)
        st.metric(
            "Dropped",
            f"{dropped:,}",
            delta=f"-{dropped}" if dropped > 0 else None,
            delta_color="inverse"
        )
    
    st.markdown("---")
    
    # Time series charts
    if len(topic_history) > 1:
        col1, col2 = st.columns(2)
        
        with col1:
            fig = create_time_series_chart(
                topic_history,
                "timestamp",
                ["queue_depth"],
                "Queue Depth Over Time",
                "Messages in Queue",
                [COLORS["orange"]]
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = create_time_series_chart(
                topic_history,
                "timestamp",
                ["batch_size_avg"],
                "Batch Size Over Time",
                "Messages per Batch",
                [COLORS["purple"]]
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Message comparison chart
        fig = create_time_series_chart(
            topic_history,
            "timestamp",
            ["messages_published", "messages_delivered", "messages_dropped"],
            "Message Counts Over Time",
            "Cumulative Count"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Collecting data for this topic...")


def page_latency(metrics: Dict[str, Any]):
    """
    Latency Visualization Page
    
    Shows:
    - Avg latency
    - P95 latency
    - P99 latency
    - Rolling latency window
    """
    st.title("⏱️ Latency Visualization")
    
    st.info("""
    **Understanding Latency Metrics:**
    
    Latency measures the time from when a message is published to when it's delivered to subscribers.
    This includes:
    - **Queueing delay**: Time spent waiting in the topic queue
    - **Batching delay**: Time waiting for batch to fill (up to 20ms)
    - **Network delay**: Time to send over WebSocket
    """)
    
    topics = metrics.get("topics", {})
    
    if not topics:
        st.warning("No topics available to show latency metrics.")
        return
    
    # Aggregate latency across all topics
    st.subheader("Per-Topic Latency")
    
    for topic_name, topic_metrics in topics.items():
        latency = topic_metrics.get("latency_ms", {})
        
        with st.expander(f"📌 {topic_name}", expanded=True):
            col1, col2, col3 = st.columns(3)
            
            avg_lat = latency.get("avg", 0)
            p95_lat = latency.get("p95", 0)
            p99_lat = latency.get("p99", 0)
            
            with col1:
                color = get_status_color(avg_lat, 50, 200)
                st.metric("Average", f"{avg_lat:.2f} ms")
            
            with col2:
                color = get_status_color(p95_lat, 100, 500)
                st.metric("P95", f"{p95_lat:.2f} ms")
            
            with col3:
                color = get_status_color(p99_lat, 200, 1000)
                st.metric("P99", f"{p99_lat:.2f} ms")
            
            # Latency over time chart
            topic_history = st.session_state.topic_history.get(topic_name, pd.DataFrame())
            if len(topic_history) > 1:
                fig = create_multi_line_chart(
                    topic_history,
                    "timestamp",
                    {
                        "latency_avg": "Average",
                        "latency_p95": "P95",
                        "latency_p99": "P99"
                    },
                    "Latency Over Time",
                    "ms"
                )
                st.plotly_chart(fig, use_container_width=True)
    
    # Latency comparison across topics
    if len(topics) > 1:
        st.markdown("---")
        st.subheader("Cross-Topic Latency Comparison")
        
        topic_names = list(topics.keys())
        avg_latencies = [topics[t].get("latency_ms", {}).get("avg", 0) for t in topic_names]
        
        fig = create_bar_chart(
            topic_names,
            avg_latencies,
            "Average Latency by Topic",
            COLORS["blue"],
            "Latency (ms)"
        )
        st.plotly_chart(fig, use_container_width=True)


def page_backpressure(metrics: Dict[str, Any]):
    """
    Backpressure Visibility Page
    
    Shows:
    - Drop count per topic
    - Drop rate over time
    - Queue saturation indicator (green/yellow/red)
    """
    st.title("⚠️ Backpressure Visibility")
    
    st.info("""
    **Understanding Backpressure:**
    
    When publishers produce messages faster than subscribers can consume them,
    the system applies backpressure by:
    1. Filling the queue until it reaches capacity
    2. Dropping oldest messages when the queue is full
    3. Disconnecting slow subscribers that can't keep up
    
    This page helps visualize when and where backpressure is occurring.
    """)
    
    topics = metrics.get("topics", {})
    
    if not topics:
        st.warning("No topics available.")
        return
    
    # Queue saturation overview
    st.subheader("Queue Saturation")
    
    cols = st.columns(min(len(topics), 4))
    
    for i, (topic_name, topic_metrics) in enumerate(topics.items()):
        queue_depth = topic_metrics.get("queue_depth", 0)
        queue_max = topic_metrics.get("queue_max_size", 10000)
        saturation = (queue_depth / queue_max * 100) if queue_max > 0 else 0
        color = get_queue_saturation_color(queue_depth, queue_max)
        
        with cols[i % len(cols)]:
            fig = create_gauge_chart(
                saturation,
                100,
                topic_name,
                "%"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Status indicator
            if saturation >= 75:
                st.error(f"🔴 Critical ({queue_depth}/{queue_max})")
            elif saturation >= 25:
                st.warning(f"🟡 Elevated ({queue_depth}/{queue_max})")
            else:
                st.success(f"🟢 Healthy ({queue_depth}/{queue_max})")
    
    st.markdown("---")
    
    # Drop counts
    st.subheader("Message Drops")
    
    topic_names = list(topics.keys())
    dropped_counts = [topics[t].get("messages_dropped", 0) for t in topic_names]
    
    if any(d > 0 for d in dropped_counts):
        fig = create_bar_chart(
            topic_names,
            dropped_counts,
            "Dropped Messages by Topic",
            COLORS["red"],
            "Dropped Count"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.success("✅ No message drops detected across all topics.")
    
    # Message flow comparison
    st.markdown("---")
    st.subheader("Message Flow Comparison")
    
    published = [topics[t].get("messages_published", 0) for t in topic_names]
    delivered = [topics[t].get("messages_delivered", 0) for t in topic_names]
    dropped = [topics[t].get("messages_dropped", 0) for t in topic_names]
    
    fig = create_comparison_bar_chart(topic_names, published, delivered, dropped)
    st.plotly_chart(fig, use_container_width=True)
    
    # Drops over time
    st.markdown("---")
    st.subheader("Drop Rate Over Time")
    
    for topic_name in topic_names:
        topic_history = st.session_state.topic_history.get(topic_name, pd.DataFrame())
        
        if len(topic_history) > 1:
            # Calculate drop rate from history
            history_with_rate = topic_history.copy()
            history_with_rate["drop_delta"] = history_with_rate["messages_dropped"].diff().fillna(0)
            history_with_rate["drop_delta"] = history_with_rate["drop_delta"].clip(lower=0)
            
            if history_with_rate["drop_delta"].sum() > 0:
                with st.expander(f"📌 {topic_name} - Drop History"):
                    fig = create_time_series_chart(
                        history_with_rate,
                        "timestamp",
                        ["drop_delta"],
                        f"Drops Over Time - {topic_name}",
                        "Drops per Second",
                        [COLORS["red"]]
                    )
                    st.plotly_chart(fig, use_container_width=True)


# ============================================================================
# Main Application
# ============================================================================

def main():
    """Main application entry point."""
    init_session_state()
    
    # Sidebar navigation
    page = render_sidebar()
    
    # Fetch latest metrics
    client = st.session_state.client
    metrics = client.fetch_metrics()
    
    if metrics is None:
        st.session_state.backend_available = False
        render_backend_unavailable()
    else:
        st.session_state.backend_available = True
        st.session_state.last_metrics = metrics
        update_history(metrics)
        
        # Render selected page
        if page == "🏠 System Overview":
            page_system_overview(metrics)
        elif page == "📈 Topic Drilldown":
            page_topic_drilldown(metrics)
        elif page == "⏱️ Latency":
            page_latency(metrics)
        elif page == "⚠️ Backpressure":
            page_backpressure(metrics)
    
    # Auto-refresh every second
    time.sleep(REFRESH_INTERVAL)
    st.rerun()


if __name__ == "__main__":
    main()
