"""
FinSight — UI Components & Styling
Injects a global design system into Streamlit.
"""

import streamlit as st

# ── Brand Colors ─────────────────────────────────────────────────────────────
COLOR_PRIMARY = "#0F52BA"    # Sapphire Blue
COLOR_SECONDARY = "#34495E"  # Dark Slate
COLOR_SUCCESS = "#27AE60"    # Emerald
COLOR_WARNING = "#F39C12"    # Orange
COLOR_DANGER = "#E74C3C"     # Alizarin Red
COLOR_BG = "#F8F9FA"         # Light Gray / Off-white


def setup_ui():
    """
    Injects custom CSS to override default Streamlit styling.
    Upgrades typography, metric cards, buttons, and layout spacing.
    """
    st.markdown("""
        <style>
        /* Typography Upgrade: Inter */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif !important;
        }

        /* Metric Cards (KPIs) styling */
        div[data-testid="metric-container"] {
            background-color: white;
            border: 1px solid #E0E6ED;
            padding: 1.25rem 1.5rem;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.03);
            transition: all 0.2s ease-in-out;
            margin-bottom: 0.5rem;
        }
        
        div[data-testid="metric-container"]:hover {
            box-shadow: 0 8px 15px rgba(0,0,0,0.06);
            transform: translateY(-2px);
            border-color: #0F52BA;
        }

        /* Metric Label */
        div[data-testid="metric-container"] > div:nth-child(1) {
            color: #64748B;
            font-weight: 500;
            font-size: 0.95rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        /* Metric Value */
        div[data-testid="metric-container"] > div:nth-child(2) {
            color: #1E293B;
            font-weight: 700;
            font-size: 2rem;
            line-height: 1.2;
            margin-top: 0.25rem;
        }

        /* Primary Button Upgrade */
        button[kind="primary"] {
            background: linear-gradient(135deg, #0F52BA 0%, #1A73E8 100%) !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            padding: 0.5rem 1.5rem !important;
            box-shadow: 0 4px 10px rgba(15, 82, 186, 0.2) !important;
            transition: all 0.2s ease !important;
        }
        button[kind="primary"]:hover {
            box-shadow: 0 6px 15px rgba(15, 82, 186, 0.3) !important;
            transform: translateY(-1px) !important;
        }

        /* Expander styling */
        .streamlit-expanderHeader {
            font-weight: 600 !important;
            color: #334155 !important;
            background-color: white;
            border-radius: 8px;
            border: 1px solid #E2E8F0;
        }

        /* Sidebar enhancement */
        section[data-testid="stSidebar"] {
            background-color: #F8FAFC !important;
            border-right: 1px solid #E2E8F0 !important;
        }
        
        /* Better tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 24px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: transparent;
            border-radius: 4px 4px 0px 0px;
            gap: 1px;
            padding-top: 10px;
            padding-bottom: 10px;
        }
        .stTabs [aria-selected="true"] {
            background-color: transparent !important;
            border-bottom: 3px solid #0F52BA !important;
            color: #0F52BA !important;
            font-weight: 600 !important;
        }

        /* DataFrame headers */
        th {
            font-size: 0.9rem !important;
            font-weight: 600 !important;
            color: #475569 !important;
            text-transform: uppercase;
        }
        </style>
    """, unsafe_allow_html=True)


def get_plotly_layout_defaults():
    """Returns a dict of consistent layout settings for all Plotly charts."""
    return dict(
        font=dict(family="Inter, sans-serif"),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=50, b=20),
        title_font=dict(size=18, color="#1E293B"),
        xaxis=dict(
            showgrid=False, 
            showline=True, 
            linecolor="#E2E8F0",
            tickfont=dict(color="#64748B")
        ),
        yaxis=dict(
            showgrid=True, 
            gridcolor="#F1F5F9", 
            showline=False,
            tickfont=dict(color="#64748B")
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#475569")
        )
    )

def apply_plotly_defaults(fig):
    """Applies the default layout and formatting to a Plotly figure."""
    fig.update_layout(**get_plotly_layout_defaults())
    fig.update_traces(
        hoverlabel=dict(
            bgcolor="white",
            font_size=13,
            font_family="Inter, sans-serif",
            bordercolor="#E2E8F0"
        )
    )
    return fig
