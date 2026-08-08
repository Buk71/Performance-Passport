import streamlit as st


# ---------------------------------------------------------------------
# Performance Passport design tokens
# ---------------------------------------------------------------------

BACKGROUND = "#F7F4EE"
SIDEBAR_BACKGROUND = "#F0ECE5"
CARD_BACKGROUND = "#FFFFFF"

TEXT_PRIMARY = "#17202A"
TEXT_SECONDARY = "#5F6B78"
TEXT_MUTED = "#89929D"

ACCENT = "#F15A24"
ACCENT_DARK = "#D74714"
ACCENT_SOFT = "#FFF0E8"

SUCCESS = "#238A52"
SUCCESS_SOFT = "#EAF6EF"

WARNING = "#D97706"
WARNING_SOFT = "#FFF5E4"

ERROR = "#C93C37"
ERROR_SOFT = "#FCECEB"

BORDER = "#E7E1D8"
SHADOW = "0 8px 24px rgba(23, 32, 42, 0.055)"

PAGE_MAX_WIDTH = 1380


def inject_global_theme():
    """Apply the Performance Passport visual design system."""

    st.markdown(
        f"""
        <style>
        :root {{
            --pp-background: {BACKGROUND};
            --pp-sidebar: {SIDEBAR_BACKGROUND};
            --pp-card: {CARD_BACKGROUND};
            --pp-text: {TEXT_PRIMARY};
            --pp-text-secondary: {TEXT_SECONDARY};
            --pp-text-muted: {TEXT_MUTED};
            --pp-accent: {ACCENT};
            --pp-accent-dark: {ACCENT_DARK};
            --pp-accent-soft: {ACCENT_SOFT};
            --pp-success: {SUCCESS};
            --pp-success-soft: {SUCCESS_SOFT};
            --pp-warning: {WARNING};
            --pp-warning-soft: {WARNING_SOFT};
            --pp-error: {ERROR};
            --pp-error-soft: {ERROR_SOFT};
            --pp-border: {BORDER};
            --pp-shadow: {SHADOW};
        }}

        html,
        body,
        .stApp,
        [class*="css"] {{
            font-family:
                Inter,
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                sans-serif;
        }}

        html,
        body,
        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"] {{
            color: var(--pp-text) !important;
            background: var(--pp-background) !important;
        }}

        [data-testid="stMainBlockContainer"] {{
            max-width: {PAGE_MAX_WIDTH}px;
            padding: 4.5rem 2.8rem 4rem;
        }}

        [data-testid="stMain"] {{
            padding-top: 0 !important;
        }}

        h1,
        h2,
        h3,
        h4,
        h5,
        h6,
        [data-testid="stMarkdownContainer"] h1,
        [data-testid="stMarkdownContainer"] h2,
        [data-testid="stMarkdownContainer"] h3 {{
            color: var(--pp-text) !important;
            letter-spacing: -0.025em;
        }}

        p,
        li,
        label,
        [data-testid="stMarkdownContainer"] p {{
            color: var(--pp-text-secondary);
        }}

        h1 {{
            margin-top: 0;
            margin-bottom: 0.4rem;
            font-size: clamp(2.1rem, 4vw, 3.25rem);
            line-height: 1.08;
            font-weight: 740;
        }}

        h2 {{
            margin-top: 1.55rem;
            margin-bottom: 0.75rem;
            font-size: 1.55rem;
            font-weight: 700;
        }}

        h3 {{
            font-size: 1.15rem;
            font-weight: 680;
        }}

        hr {{
            margin: 1.5rem 0;
            border: 0;
            border-top: 1px solid var(--pp-border);
        }}

        [data-testid="stHeader"] {{
            background: rgba(247, 244, 238, 0.90);
            backdrop-filter: blur(12px);
        }}

        [data-testid="stSidebar"] {{
            background: var(--pp-sidebar);
            border-right: 1px solid rgba(23, 32, 42, 0.06);
        }}

        [data-testid="stSidebarContent"] {{
            padding: 1.25rem 0.9rem 1.25rem;
        }}

        [data-testid="stSidebar"] .stRadio > label {{
            position: absolute;
            width: 1px;
            height: 1px;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
        }}

        [data-testid="stSidebar"] .stRadio div[role="radiogroup"] {{
            gap: 0.22rem;
        }}

        [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"] {{
            width: 100%;
            min-height: 2.65rem;
            padding: 0.62rem 0.75rem;
            border-radius: 11px;
            transition:
                background-color 150ms ease,
                transform 150ms ease;
        }}

        [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"]:hover {{
            background: rgba(255, 255, 255, 0.62);
            transform: translateX(2px);
        }}

        [data-testid="stSidebar"]
        .stRadio
        label[data-baseweb="radio"]:has(input:checked) {{
            background: var(--pp-accent);
            box-shadow: 0 6px 17px rgba(241, 90, 36, 0.20);
        }}

        [data-testid="stSidebar"]
        .stRadio
        label[data-baseweb="radio"]:has(input:checked)
        p {{
            color: white !important;
            font-weight: 670;
        }}

        [data-testid="stSidebar"]
        .stRadio
        div[role="radiogroup"]
        > label
        > div:first-child {{
            display: none;
        }}

        [data-baseweb="select"] > div,
        [data-baseweb="input"] > div,
        [data-baseweb="textarea"] > div {{
            color: var(--pp-text);
            background: var(--pp-card);
            border-color: var(--pp-border);
            border-radius: 11px;
        }}

        [data-baseweb="select"] > div:focus-within,
        [data-baseweb="input"] > div:focus-within,
        [data-baseweb="textarea"] > div:focus-within {{
            border-color: var(--pp-accent);
            box-shadow: 0 0 0 3px rgba(241, 90, 36, 0.12);
        }}

        .stButton > button,
        .stDownloadButton > button {{
            min-height: 2.65rem;
            padding: 0.6rem 1.1rem;
            color: white;
            font-weight: 660;
            background: var(--pp-accent);
            border: 0;
            border-radius: 11px;
            box-shadow: 0 5px 14px rgba(241, 90, 36, 0.20);
        }}

        .stButton > button:hover,
        .stDownloadButton > button:hover {{
            color: white;
            background: var(--pp-accent-dark);
        }}

        [data-testid="stMetric"] {{
            min-height: 0;
            padding: 0.75rem;
            background: var(--pp-card);
            border: 1px solid var(--pp-border);
            border-radius: 13px;
            box-shadow: none;
        }}

        [data-testid="stMetricValue"] {{
            color: var(--pp-text);
            font-size: 1.25rem;
            font-weight: 700;
        }}

        .pp-brand {{
            display: flex;
            align-items: center;
            gap: 0.7rem;
            margin: 0.15rem 0 1.25rem;
            padding: 0 0.25rem;
        }}

        .pp-brand-mark {{
            display: grid;
            place-items: center;
            width: 2.65rem;
            height: 2.65rem;
            flex: 0 0 2.65rem;
            color: white !important;
            font-size: 0.88rem;
            font-weight: 780;
            background: var(--pp-accent);
            border-radius: 50%;
            box-shadow: 0 6px 16px rgba(241, 90, 36, 0.25);
        }}

        .pp-brand-title {{
            color: var(--pp-text) !important;
            font-size: 0.98rem;
            font-weight: 730;
            line-height: 1.12;
        }}

        .pp-brand-subtitle {{
            margin-top: 0.2rem;
            color: var(--pp-text-secondary) !important;
            font-size: 0.7rem;
            line-height: 1.25;
        }}

        .pp-sidebar-section {{
            margin: 0.25rem 0 0.45rem;
            padding: 0 0.55rem;
            color: var(--pp-text-muted);
            font-size: 0.66rem;
            font-weight: 730;
            letter-spacing: 0.09em;
            text-transform: uppercase;
        }}

        .pp-sidebar-footer {{
            margin-top: 1rem;
            padding: 0.85rem;
            background: rgba(255, 255, 255, 0.58);
            border: 1px solid rgba(23, 32, 42, 0.06);
            border-radius: 13px;
        }}

        .pp-sidebar-footer-label {{
            color: var(--pp-text-muted);
            font-size: 0.64rem;
            font-weight: 720;
            letter-spacing: 0.07em;
            text-transform: uppercase;
        }}

        .pp-sidebar-footer-title {{
            margin-top: 0.25rem;
            color: var(--pp-text);
            font-size: 0.84rem;
            font-weight: 680;
        }}

        .pp-sidebar-footer-meta {{
            margin-top: 0.12rem;
            color: var(--pp-text-secondary);
            font-size: 0.7rem;
        }}

        .pp-page-header {{
            margin-bottom: 1.35rem;
        }}

        .pp-page-eyebrow {{
            margin-bottom: 0.42rem;
            color: var(--pp-accent);
            font-size: 0.72rem;
            font-weight: 760;
            letter-spacing: 0.09em;
            text-transform: uppercase;
        }}

        .pp-page-title {{
            color: var(--pp-text) !important;
            font-size: clamp(2.15rem, 4vw, 3.25rem);
            font-weight: 750;
            line-height: 1.08;
            letter-spacing: -0.038em;
        }}

        .pp-page-intro {{
            max-width: 720px;
            margin-top: 0.62rem;
            color: var(--pp-text-secondary);
            font-size: 1rem;
            line-height: 1.55;
        }}

        .pp-page-intro strong {{
            color: var(--pp-text);
        }}

        .pp-card {{
            height: 100%;
            padding: 1.15rem 1.2rem;
            background: var(--pp-card);
            border: 1px solid rgba(23, 32, 42, 0.065);
            border-radius: 17px;
            box-shadow: var(--pp-shadow);
        }}

        .pp-card-hero {{
            padding: 1.35rem 1.4rem;
        }}

        .pp-card-accent {{
            background:
                linear-gradient(
                    135deg,
                    rgba(241, 90, 36, 0.10),
                    rgba(255, 255, 255, 0.95) 52%
                ),
                var(--pp-card);
        }}

        .pp-card-label {{
            color: var(--pp-text-muted);
            font-size: 0.68rem;
            font-weight: 760;
            letter-spacing: 0.085em;
            text-transform: uppercase;
        }}

        .pp-card-title {{
            margin-top: 0.42rem;
            color: var(--pp-text);
            font-size: 1.22rem;
            font-weight: 710;
            letter-spacing: -0.02em;
        }}

        .pp-card-copy {{
            margin-top: 0.48rem;
            color: var(--pp-text-secondary);
            font-size: 0.91rem;
            line-height: 1.5;
        }}

        .pp-card-copy strong {{
            color: var(--pp-text);
        }}

        .pp-large-value {{
            color: var(--pp-text);
            font-size: clamp(2rem, 4vw, 3rem);
            font-weight: 760;
            line-height: 1;
            letter-spacing: -0.045em;
        }}

        .pp-large-value-accent {{
            color: var(--pp-accent);
        }}

        .pp-unit {{
            margin-left: 0.18rem;
            color: var(--pp-text-secondary);
            font-size: 0.86rem;
            font-weight: 620;
        }}

        .pp-small-meta {{
            margin-top: 0.35rem;
            color: var(--pp-text-secondary);
            font-size: 0.76rem;
            line-height: 1.4;
        }}

        .pp-progress-track {{
            height: 0.48rem;
            margin-top: 0.9rem;
            overflow: hidden;
            background: #ECE7DF;
            border-radius: 999px;
        }}

        .pp-progress-fill {{
            height: 100%;
            background: var(--pp-accent);
            border-radius: 999px;
        }}

        .pp-status {{
            display: inline-flex;
            align-items: center;
            padding: 0.28rem 0.52rem;
            color: var(--pp-success);
            font-size: 0.7rem;
            font-weight: 720;
            background: var(--pp-success-soft);
            border-radius: 999px;
        }}

        .pp-status-warning {{
            color: var(--pp-warning);
            background: var(--pp-warning-soft);
        }}

        .pp-stat-card {{
            min-height: 94px;
            padding: 0.88rem 0.95rem;
            background: var(--pp-card);
            border: 1px solid rgba(23, 32, 42, 0.065);
            border-radius: 14px;
            box-shadow: 0 5px 16px rgba(23, 32, 42, 0.035);
        }}

        .pp-stat-label {{
            color: var(--pp-text-muted);
            font-size: 0.67rem;
            font-weight: 740;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }}

        .pp-stat-value {{
            margin-top: 0.32rem;
            color: var(--pp-text);
            font-size: 1.28rem;
            font-weight: 730;
            letter-spacing: -0.03em;
        }}

        .pp-stat-context {{
            margin-top: 0.24rem;
            color: var(--pp-text-secondary);
            font-size: 0.72rem;
            line-height: 1.3;
        }}

        .pp-training-card {{
            margin-top: 0.78rem;
            padding: 1rem 1.05rem;
            border: 1px solid var(--pp-border);
            border-radius: 14px;
            background: rgba(255, 255, 255, 0.72);
        }}

        .pp-training-card-top {{
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            align-items: flex-start;
        }}

        .pp-training-date {{
            color: var(--pp-text-muted);
            font-size: 0.70rem;
            font-weight: 720;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }}

        .pp-training-title {{
            margin-top: 0.12rem;
            color: var(--pp-text);
            font-size: 0.98rem;
            font-weight: 740;
            letter-spacing: -0.015em;
        }}

        .pp-training-location {{
            margin-top: 0.18rem;
            color: var(--pp-text-secondary);
            font-size: 0.75rem;
        }}

        .pp-training-badge {{
            flex: 0 0 auto;
            max-width: 260px;
            padding: 0.34rem 0.58rem;
            border-radius: 999px;
            background: var(--pp-success-soft);
            color: var(--pp-success);
            font-size: 0.72rem;
            font-weight: 760;
            text-align: center;
        }}

        .pp-training-facts {{
            margin-top: 0.72rem;
            color: var(--pp-text);
            font-size: 0.81rem;
            font-weight: 650;
            line-height: 1.5;
        }}

        .pp-training-environment {{
            margin-top: 0.40rem;
            color: var(--pp-text-secondary);
            font-size: 0.77rem;
            line-height: 1.5;
        }}

        .pp-training-recognition {{
            margin-top: 0.70rem;
            padding-top: 0.66rem;
            border-top: 1px solid var(--pp-border);
            color: var(--pp-text-secondary);
            font-size: 0.77rem;
            line-height: 1.5;
        }}

        .pp-training-recognition strong {{
            color: var(--pp-text);
            margin-right: 0.42rem;
        }}

        .pp-training-positive {{
            margin-top: 0.24rem;
            color: var(--pp-text-secondary);
        }}

        .pp-activity-row {{
            display: grid;
            grid-template-columns: 80px minmax(170px, 1fr) 105px 105px 90px;
            gap: 0.75rem;
            align-items: center;
            padding: 0.82rem 0;
            border-bottom: 1px solid var(--pp-border);
        }}

        .pp-activity-row:last-child {{
            border-bottom: 0;
        }}

        .pp-activity-date {{
            color: var(--pp-text-secondary);
            font-size: 0.76rem;
        }}

        .pp-activity-name {{
            color: var(--pp-text);
            font-size: 0.88rem;
            font-weight: 690;
        }}

        .pp-activity-detail {{
            color: var(--pp-text-secondary);
            font-size: 0.77rem;
        }}

        .pp-placeholder {{
            max-width: 760px;
            margin-top: 1.5rem;
            padding: 1.8rem;
            background: var(--pp-card);
            border: 1px solid var(--pp-border);
            border-radius: 17px;
            box-shadow: var(--pp-shadow);
        }}

        .pp-placeholder-eyebrow {{
            color: var(--pp-accent);
            font-size: 0.7rem;
            font-weight: 730;
            letter-spacing: 0.09em;
            text-transform: uppercase;
        }}

        .pp-placeholder-title {{
            margin-top: 0.5rem;
            color: var(--pp-text);
            font-size: 1.35rem;
            font-weight: 710;
        }}

        .pp-placeholder-copy {{
            margin-top: 0.55rem;
            color: var(--pp-text-secondary);
            font-size: 0.93rem;
            line-height: 1.55;
        }}

        @media (max-width: 900px) {{
            [data-testid="stMainBlockContainer"] {{
                padding: 4rem 1rem 3rem;
            }}

            .pp-training-card-top {{
                display: block;
            }}

            .pp-training-badge {{
                display: inline-block;
                margin-top: 0.55rem;
                max-width: 100%;
                text-align: left;
            }}

            .pp-training-facts,
            .pp-training-environment,
            .pp-training-recognition {{
                display: block;
            }}

            .pp-activity-row {{
                grid-template-columns: 62px 1fr;
            }}

            .pp-activity-detail {{
                display: none;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_placeholder(title, question, description):
    """Render a polished placeholder for screens not yet implemented."""

    st.markdown(
        f"""
        <div class="pp-placeholder">
            <div class="pp-placeholder-eyebrow">Design Edition</div>
            <div class="pp-placeholder-title">{title}</div>
            <div class="pp-placeholder-copy">
                <strong>{question}</strong><br><br>
                {description}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )