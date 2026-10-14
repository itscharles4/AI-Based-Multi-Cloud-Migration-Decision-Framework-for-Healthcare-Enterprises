"""
dashboard/app.py  --  Streamlit Dashboard
==========================================
Standing in for Amazon QuickSight, this dashboard provides:
  - Login screen (mock Cognito auth)
  - Routing distribution chart (EDGE vs CLOUD donut)
  - Live-updating predicted latency trend chart
  - Criticality vs Routing scatter plot
  - Key metrics row (totals, percentages, overrides)
  - Recent events table with colour-coded routing decisions
  - Auto-refresh (configurable interval)

Run with:
  streamlit run dashboard/app.py

Login: admin / hospital123

Prerequisites:
  - Run simulation first to populate the DB:
    python src/api/simulate_stream.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import pandas as pd
import time

# Page configuration -- must be the FIRST Streamlit call
st.set_page_config(
    page_title="Telemedicine Workload Offloader",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

from src.execution.auth    import login, verify_token
from src.execution.storage import init_db, get_recent_hot_records, get_routing_distribution

init_db()

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .main-header {
        background: linear-gradient(135deg, #0d1b2a 0%, #1b263b 50%, #0d47a1 100%);
        border-radius: 12px;
        padding: 24px 32px;
        margin-bottom: 24px;
        color: white;
    }

    .main-header h1 {
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.5px;
    }

    .main-header p {
        margin: 6px 0 0 0;
        opacity: 0.75;
        font-size: 0.9rem;
    }

    .metric-card {
        background: linear-gradient(135deg, #1e2a3a, #243447);
        border: 1px solid #2d4060;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }

    .stMetric > label {
        font-size: 0.8rem !important;
        color: #8da9c4 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .stMetric > div {
        font-size: 2rem !important;
        font-weight: 700 !important;
    }

    .section-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #e0e0e0;
        border-left: 4px solid #1565c0;
        padding-left: 12px;
        margin: 20px 0 12px 0;
    }

    .info-box {
        background: linear-gradient(135deg, #0d1b2a, #1b263b);
        border: 1px solid #2d4060;
        border-radius: 8px;
        padding: 16px;
        color: #8da9c4;
        font-size: 0.85rem;
    }

    div[data-testid="stDataFrame"] {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------
def is_logged_in() -> bool:
    token = st.session_state.get("auth_token")
    if not token:
        return False
    return verify_token(token) is not None


def do_login(username: str, password: str) -> bool:
    token = login(username, password)
    if token:
        st.session_state["auth_token"] = token
        return True
    return False


# ---------------------------------------------------------------------------
# Login Page
# ---------------------------------------------------------------------------
def render_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style='text-align:center; padding: 40px 0 20px 0;'>
            <div style='font-size:3rem;'>🏥</div>
            <h2 style='color:#e0e0e0; margin:8px 0 4px 0;'>Telemedicine Offloader</h2>
            <p style='color:#8da9c4; font-size:0.9rem;'>Cloud Architecture Dashboard — BCSE355L</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            st.markdown("### Sign In")
            username = st.text_input("Username", value="admin", placeholder="admin")
            password = st.text_input("Password", type="password", placeholder="hospital123")
            submitted = st.form_submit_button("Sign In →", use_container_width=True)

        if submitted:
            if do_login(username, password):
                st.success("✓ Login successful")
                st.rerun()
            else:
                st.error("❌ Invalid credentials. Use admin / hospital123")

        st.markdown("""
        <div style='text-align:center; margin-top:20px;'>
            <small style='color:#5a7a9a;'>Demo credentials: admin / hospital123<br>
            Secured by mock Cognito auth layer</small>
        </div>
        """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------
def _build_pie_chart(distribution: dict):
    """EDGE vs CLOUD donut chart."""
    import plotly.graph_objects as go
    labels = list(distribution.keys())
    values = list(distribution.values())
    colors = []
    for label in labels:
        colors.append("#ef5350" if label == "EDGE" else "#1565c0")

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.50,
        marker=dict(colors=colors),
        textinfo="label+percent",
        textfont=dict(size=14, color="white"),
    )])
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e0e0e0"),
        margin=dict(t=10, b=10, l=10, r=10),
        showlegend=True,
        legend=dict(font=dict(color="#e0e0e0")),
    )
    return fig


def _build_latency_trend(df: pd.DataFrame):
    """Predicted latency line chart with EDGE/CLOUD decision markers."""
    import plotly.graph_objects as go

    chart_df = df[["stored_at", "predicted_latency_ms", "routing_decision"]].copy()
    chart_df = chart_df.sort_values("stored_at").tail(100)
    chart_df["stored_at"] = pd.to_datetime(chart_df["stored_at"])

    edge_pts  = chart_df[chart_df["routing_decision"] == "EDGE"]
    cloud_pts = chart_df[chart_df["routing_decision"] == "CLOUD"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=chart_df["stored_at"], y=chart_df["predicted_latency_ms"],
        mode="lines", name="Predicted Latency",
        line=dict(color="#42a5f5", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=edge_pts["stored_at"], y=edge_pts["predicted_latency_ms"],
        mode="markers", name="EDGE decision",
        marker=dict(color="#ef5350", size=8, symbol="x"),
    ))
    fig.add_trace(go.Scatter(
        x=cloud_pts["stored_at"], y=cloud_pts["predicted_latency_ms"],
        mode="markers", name="CLOUD decision",
        marker=dict(color="#66bb6a", size=6),
    ))
    fig.add_hline(y=75,  line_dash="dot", line_color="#ffeb3b",
                  annotation_text="LOW/MEDIUM (75ms)")
    fig.add_hline(y=150, line_dash="dot", line_color="#ff7043",
                  annotation_text="MEDIUM/HIGH (150ms)")
    fig.add_hline(y=300, line_dash="dot", line_color="#ef5350",
                  annotation_text="Degradation Veto (300ms)")
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(13,27,42,0.7)",
        font=dict(color="#e0e0e0"),
        xaxis=dict(gridcolor="#2d4060", title="Time"),
        yaxis=dict(gridcolor="#2d4060", title="Predicted Latency (ms)"),
        margin=dict(t=10, b=40, l=10, r=10),
        legend=dict(font=dict(color="#e0e0e0"), bgcolor="rgba(0,0,0,0)"),
    )
    return fig


def _build_criticality_scatter(df: pd.DataFrame):
    """Criticality vs Predicted Latency scatter, coloured by routing decision."""
    import plotly.graph_objects as go

    if "patient_criticality_score" not in df.columns or "predicted_latency_ms" not in df.columns:
        return None

    edge_pts  = df[df["routing_decision"] == "EDGE"]
    cloud_pts = df[df["routing_decision"] == "CLOUD"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=edge_pts["patient_criticality_score"],
        y=edge_pts["predicted_latency_ms"],
        mode="markers", name="EDGE",
        marker=dict(color="#ef5350", size=7, opacity=0.8, symbol="x"),
    ))
    fig.add_trace(go.Scatter(
        x=cloud_pts["patient_criticality_score"],
        y=cloud_pts["predicted_latency_ms"],
        mode="markers", name="CLOUD",
        marker=dict(color="#42a5f5", size=7, opacity=0.8),
    ))
    # Emergency override zone
    fig.add_vrect(x0=9.0, x1=10.0, fillcolor="#ef535015", line_width=0,
                  annotation_text="Override zone", annotation_position="top left")
    fig.add_hline(y=300, line_dash="dot", line_color="#ef5350",
                  annotation_text="300ms veto")
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(13,27,42,0.7)",
        font=dict(color="#e0e0e0"),
        xaxis=dict(gridcolor="#2d4060", title="Patient Criticality Score (0-10)", range=[-0.2, 10.2]),
        yaxis=dict(gridcolor="#2d4060", title="Predicted Latency (ms)"),
        margin=dict(t=10, b=40, l=10, r=10),
        legend=dict(font=dict(color="#e0e0e0"), bgcolor="rgba(0,0,0,0)"),
    )
    return fig


def _build_reason_bar(df: pd.DataFrame):
    """Bar chart of routing reasons."""
    import plotly.graph_objects as go

    if "reason" not in df.columns:
        return None

    counts = df["reason"].value_counts()
    color_map = {
        "ahp_decision":               "#42a5f5",
        "override_critical_patient":  "#ef5350",
        "network_degradation_veto":   "#ff7043",
    }
    colors = [color_map.get(r, "#78909c") for r in counts.index]

    fig = go.Figure(go.Bar(
        x=counts.index.tolist(),
        y=counts.values.tolist(),
        marker_color=colors,
        text=counts.values.tolist(),
        textposition="outside",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(13,27,42,0.7)",
        font=dict(color="#e0e0e0"),
        xaxis=dict(gridcolor="#2d4060", title="Decision Reason"),
        yaxis=dict(gridcolor="#2d4060", title="Count"),
        margin=dict(t=10, b=80, l=10, r=10),
    )
    return fig


# ---------------------------------------------------------------------------
# Main Dashboard
# ---------------------------------------------------------------------------
def render_dashboard():
    # --- Header ---
    st.markdown("""
    <div class="main-header">
        <h1>🏥 Telemedicine Workload Offloader</h1>
        <p>AI-Based Multi-Cloud Routing Dashboard &nbsp;|&nbsp; BCSE355L Cloud Architecture Design</p>
    </div>
    """, unsafe_allow_html=True)

    # --- Sidebar ---
    with st.sidebar:
        st.markdown("### 🔧 Controls")

        # Auto-refresh
        auto_refresh = st.checkbox("⚡ Auto-refresh", value=False)
        refresh_interval = st.slider("Refresh interval (sec)", 5, 60, 10, step=5,
                                     disabled=not auto_refresh)

        if st.button("🔄 Refresh Now", use_container_width=True):
            st.rerun()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.pop("auth_token", None)
            st.rerun()

        st.markdown("---")
        st.markdown("**System Info**")
        st.caption("Storage: SQLite (sim DynamoDB)")
        st.caption("Auth: Mock Cognito")
        st.caption("Logger: RotatingFile (sim CloudWatch)")
        st.markdown("---")
        st.markdown("**Team**")
        st.caption("Charles (24BIT0522) — LSTM")
        st.caption("Tanmay (24BIT0079) — AHP")
        st.caption("Rani (24BIT0543) — Execution")
        st.markdown("---")
        st.caption("AWS Migration: Replace each local component with the service shown in docs/research/architecture_notes.md")

    # --- Load data ---
    records      = get_recent_hot_records(limit=500)
    distribution = get_routing_distribution()

    if not records:
        st.info(
            "📭 No events yet. Run the simulation:\n"
            "```\n"
            "# Terminal 1:\n"
            "uvicorn src.api.main:app --reload\n\n"
            "# Terminal 2:\n"
            "python src/api/simulate_stream.py\n"
            "```"
        )
        return

    df = pd.DataFrame(records)

    # --- Metrics row ---
    total_all = sum(distribution.values()) if distribution else 0
    total_all = max(total_all, 1)
    edge_n    = distribution.get("EDGE",  0)
    cloud_n   = distribution.get("CLOUD", 0)

    st.markdown('<div class="section-header">📊 Key Metrics</div>', unsafe_allow_html=True)
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Total Events", f"{total_all:,}")
    with m2:
        st.metric("Routed to EDGE", f"{edge_n:,}", f"{edge_n/total_all*100:.1f}%")
    with m3:
        st.metric("Routed to CLOUD", f"{cloud_n:,}", f"{cloud_n/total_all*100:.1f}%")
    with m4:
        overrides = len(df[df["reason"] == "override_critical_patient"]) if "reason" in df else 0
        st.metric("🚨 Emergency Overrides", f"{overrides}")
    with m5:
        vetocount = len(df[df["reason"] == "network_degradation_veto"]) if "reason" in df else 0
        st.metric("⚠️ Network Vetoes", f"{vetocount}")

    st.markdown("---")

    # --- Row 1: Latency trend + Pie chart ---
    col_chart, col_dist = st.columns([2, 1])

    with col_dist:
        st.markdown('<div class="section-header">🥧 Routing Distribution</div>', unsafe_allow_html=True)
        if distribution:
            st.plotly_chart(_build_pie_chart(distribution), use_container_width=True)
        else:
            st.info("No distribution data yet.")

    with col_chart:
        st.markdown('<div class="section-header">📈 Predicted Latency Trend (last 100)</div>', unsafe_allow_html=True)
        if "predicted_latency_ms" in df.columns and "stored_at" in df.columns:
            st.plotly_chart(_build_latency_trend(df), use_container_width=True)

    st.markdown("---")

    # --- Row 2: Criticality scatter + Reason bar ---
    col_scatter, col_bar = st.columns(2)

    with col_scatter:
        st.markdown('<div class="section-header">🎯 Criticality vs Latency</div>', unsafe_allow_html=True)
        fig_scatter = _build_criticality_scatter(df)
        if fig_scatter:
            st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.info("Not enough data for scatter plot.")

    with col_bar:
        st.markdown('<div class="section-header">📋 Decision Reasons</div>', unsafe_allow_html=True)
        fig_bar = _build_reason_bar(df)
        if fig_bar:
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No reason data available.")

    st.markdown("---")

    # --- Recent Events Table ---
    st.markdown('<div class="section-header">📋 Recent Events (last 20)</div>', unsafe_allow_html=True)

    display_cols = ["device_id", "timestamp", "routing_decision", "reason",
                    "predicted_latency_ms", "patient_criticality_score", "stored_at"]
    display_df   = df[[c for c in display_cols if c in df.columns]].head(20)

    def colour_decision(val):
        if val == "EDGE":
            return "background-color: #7f0000; color: white; font-weight: bold"
        return "background-color: #0a3055; color: white; font-weight: bold"

    def colour_reason(val):
        if val == "override_critical_patient":
            return "background-color: #7f0000; color: white"
        elif val == "network_degradation_veto":
            return "background-color: #5d2e00; color: white"
        return ""

    styled = (display_df.style
              .map(colour_decision, subset=["routing_decision"])
              .map(colour_reason,   subset=["reason"]))
    st.dataframe(styled, use_container_width=True, height=420)

    st.caption(f"Showing {len(display_df)} of {total_all} total events. "
               f"Last updated: {pd.Timestamp.now().strftime('%H:%M:%S')}")

    # --- Auto-refresh ---
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()


# ---------------------------------------------------------------------------
# App entry point
# ---------------------------------------------------------------------------
if is_logged_in():
    render_dashboard()
else:
    render_login()
