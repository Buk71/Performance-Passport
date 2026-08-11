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
        
        /* PERFORMANCE PASSPORT DESIGN SYSTEM v1 */
        :root {{
            --pp-ink: #10263D;
            --pp-paper: #F7F3EC;
            --pp-orange: #F05A28;
            --pp-green: #3E8E72;
            --pp-green-soft: #E6F1EC;
            --pp-line: rgba(16, 38, 61, 0.10);
        }}
        .pp-v21-kicker{{color:var(--pp-orange);font-size:.72rem;font-weight:800;letter-spacing:.13em;text-transform:uppercase}}
        .pp-v21-title{{margin-top:.22rem;color:var(--pp-ink);font-size:clamp(2rem,4.5vw,3.6rem);font-weight:800;line-height:1;letter-spacing:-.055em}}
        .pp-v21-subtitle{{margin-top:.5rem;max-width:760px;color:var(--pp-text-secondary);font-size:.96rem;line-height:1.55}}
        .pp-v21-section-title{{margin:1.45rem 0 .72rem;color:var(--pp-ink);font-size:1.12rem;font-weight:780;letter-spacing:-.02em}}
        .pp-v21-week{{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:.55rem;margin:0 0 1rem}}
        .pp-v21-day{{min-height:92px;padding:.72rem .68rem;background:rgba(255,255,255,.72);border:1px solid var(--pp-line);border-radius:15px}}
        .pp-v21-day.today{{background:var(--pp-ink);border-color:var(--pp-ink);box-shadow:0 10px 24px rgba(16,38,61,.15)}}
        .pp-v21-day.completed{{background:var(--pp-green-soft);border-color:rgba(62,142,114,.20)}}
        .pp-v21-day-name{{color:var(--pp-text-muted);font-size:.65rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase}}
        .pp-v21-day-session{{margin-top:.45rem;color:var(--pp-ink);font-size:.82rem;font-weight:760;line-height:1.2}}
        .pp-v21-day-detail{{margin-top:.22rem;color:var(--pp-text-secondary);font-size:.68rem;line-height:1.25}}
        .pp-v21-day.today .pp-v21-day-name,.pp-v21-day.today .pp-v21-day-detail{{color:rgba(255,255,255,.70)}}
        .pp-v21-day.today .pp-v21-day-session{{color:white}}
        .pp-v21-grid{{display:grid;grid-template-columns:minmax(0,1.12fr) minmax(0,.88fr);gap:1rem;margin-top:1rem}}
        .pp-v21-card{{position:relative;overflow:hidden;min-height:100%;padding:1.25rem 1.3rem;background:rgba(255,255,255,.88);border:1px solid var(--pp-line);border-radius:22px;box-shadow:0 10px 32px rgba(16,38,61,.055)}}
        .pp-v21-card.dark{{color:white;background:var(--pp-ink);border-color:var(--pp-ink)}}
        .pp-v21-card.route::after{{content:"";position:absolute;inset:0;opacity:.15;pointer-events:none;background-image:radial-gradient(ellipse at 85% 30%,transparent 0 18%,rgba(240,90,40,.55) 18.5% 19%,transparent 19.5% 26%,rgba(240,90,40,.35) 26.5% 27%,transparent 27.5%),radial-gradient(ellipse at 75% 85%,transparent 0 24%,rgba(16,38,61,.22) 24.5% 25%,transparent 25.5% 34%,rgba(16,38,61,.16) 34.5% 35%,transparent 35.5%)}}
        .pp-v21-label{{color:var(--pp-text-muted);font-size:.67rem;font-weight:800;letter-spacing:.10em;text-transform:uppercase}}
        .pp-v21-card.dark .pp-v21-label{{color:rgba(255,255,255,.58)}}
        .pp-v21-card-title{{margin-top:.42rem;color:var(--pp-ink);font-size:1.32rem;font-weight:790;letter-spacing:-.025em}}
        .pp-v21-card.dark .pp-v21-card-title{{color:white}}
        .pp-v21-copy{{margin-top:.42rem;color:var(--pp-text-secondary);font-size:.82rem;line-height:1.48}}
        .pp-v21-card.dark .pp-v21-copy{{color:rgba(255,255,255,.72)}}
        .pp-v21-predictions{{display:grid;grid-template-columns:repeat(3,1fr);gap:.7rem;margin-top:.9rem}}
        .pp-v21-pred{{padding-right:.7rem;border-right:1px solid rgba(255,255,255,.13)}}
        .pp-v21-pred:last-child{{border-right:0}}
        .pp-v21-pred-value{{color:white;font-size:clamp(1.5rem,3vw,2.35rem);font-weight:820;letter-spacing:-.055em;line-height:1}}
        .pp-v21-pred-value.orange{{color:var(--pp-orange)}} .pp-v21-pred-value.green{{color:#75C4A6}}
        .pp-v21-pred-label{{margin-top:.32rem;color:rgba(255,255,255,.54);font-size:.61rem;font-weight:780;letter-spacing:.08em;text-transform:uppercase}}
        .pp-v21-pill{{display:inline-flex;margin-top:.75rem;padding:.35rem .58rem;color:var(--pp-green);background:var(--pp-green-soft);border-radius:999px;font-size:.7rem;font-weight:760}}
        .pp-v21-pathmark{{width:43px;height:43px;flex:0 0 43px}}
        .pp-v21-motto{{margin-top:.16rem;color:var(--pp-text-secondary);font-size:.66rem;font-weight:560}}
        @media(max-width:900px){{
            [data-testid="stMainBlockContainer"]{{padding:3.9rem 1rem 5.8rem!important;}}
            .pp-v21-week{{grid-template-columns:repeat(7,minmax(78px,1fr));overflow-x:auto;padding-bottom:.25rem;scrollbar-width:none;}}
            .pp-v21-week::-webkit-scrollbar{{display:none;}}
            .pp-v21-grid{{grid-template-columns:1fr;}}
        }}
        @media(max-width:640px){{
            .pp-v21-title{{font-size:2.15rem;}}
            .pp-v21-card{{padding:1.05rem;border-radius:18px;}}
            .pp-v21-pred-value{{font-size:1.55rem;}}
            .pp-v21-pred-label{{font-size:.55rem;}}
        }}




        /* v0.22.3 COACH HOME COMPOSITION */
        .pp-brand-pathmark {{width:52px;height:40px;object-fit:contain;flex:0 0 52px;}}
        .pp-v22-head {{margin-bottom:1.15rem;}}
        .pp-v22-section-label {{margin-bottom:.50rem;color:var(--pp-ink);font-size:.72rem;font-weight:840;letter-spacing:.11em;text-transform:uppercase;}}

        .pp-v223-home-grid {{display:grid;grid-template-columns:minmax(0,1.56fr) minmax(340px,.66fr);gap:1.45rem;align-items:start;}}
        .pp-v223-coach-column {{display:flex;flex-direction:column;gap:.70rem;min-width:0;}}
        .pp-v223-athlete-column {{position:sticky;top:1rem;min-width:0;}}

        .pp-v22-week {{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:.45rem;margin-bottom:0;}}
        .pp-v22-day {{min-height:72px;padding:.66rem .62rem;border:1px solid var(--pp-line);border-radius:14px;background:rgba(255,255,255,.82);}}
        .pp-v22-day span {{display:block;color:var(--pp-text-muted);font-size:.61rem;font-weight:820;letter-spacing:.08em;text-transform:uppercase;}}
        .pp-v22-day strong {{display:block;margin-top:.38rem;color:var(--pp-ink);font-size:.76rem;font-weight:800;line-height:1.15;}}
        .pp-v22-day.completed {{background:rgba(62,142,114,.075);border-color:rgba(62,142,114,.16);}}
        .pp-v22-day.today {{background:var(--pp-ink);border-color:var(--pp-ink);box-shadow:0 9px 21px rgba(16,38,61,.13);}}
        .pp-v22-day.today span {{color:rgba(255,255,255,.60);}}
        .pp-v22-day.today strong {{color:#fff;}}

        .pp-v223-upnext-row {{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(250px,.75fr);gap:.62rem;}}
        .pp-v22-upnext {{position:relative;overflow:hidden;padding:.84rem .96rem .78rem;border:1px solid var(--pp-line);border-radius:16px;background:radial-gradient(ellipse at 102% 116%,rgba(240,90,40,.12) 0 17%,transparent 17.5% 27%,rgba(240,90,40,.06) 27.5% 28.5%,transparent 29%),rgba(255,255,255,.92);box-shadow:0 7px 22px rgba(16,38,61,.04);}}
        .pp-v22-upnext-title {{margin:.22rem 0 .10rem;color:var(--pp-ink);font-size:1.12rem;font-weight:830;letter-spacing:-.03em;}}
        .pp-v22-upnext .pp-v21-copy {{margin-top:.12rem;font-size:.72rem;line-height:1.34;}}
        .pp-v22-text-link {{display:inline-block;margin-top:.42rem;color:var(--pp-orange);font-size:.67rem;font-weight:790;text-decoration:none;}}

        .pp-v223-trajectory {{display:flex;flex-direction:column;justify-content:center;padding:.82rem .92rem;color:var(--pp-ink);text-decoration:none;border:1px solid var(--pp-line);border-radius:16px;background:linear-gradient(135deg,rgba(62,142,114,.08),rgba(255,255,255,.88));}}
        .pp-v223-trajectory span,.pp-v223-compact span {{color:var(--pp-text-muted);font-size:.56rem;font-weight:820;letter-spacing:.09em;text-transform:uppercase;}}
        .pp-v223-trajectory strong {{margin-top:.28rem;color:var(--pp-ink);font-size:.78rem;line-height:1.28;}}
        .pp-v223-trajectory small {{margin-top:.36rem;color:var(--pp-green);font-size:.61rem;font-weight:720;}}

        .pp-v223-panel {{padding:.82rem .92rem .88rem;border:1px solid var(--pp-line);border-radius:16px;background:rgba(255,255,255,.82);}}
        .pp-v223-panel-head {{display:flex;align-items:flex-end;justify-content:space-between;gap:1rem;margin-bottom:.65rem;}}
        .pp-v223-panel-head span {{display:block;color:var(--pp-text-muted);font-size:.55rem;font-weight:820;letter-spacing:.09em;text-transform:uppercase;}}
        .pp-v223-panel-head strong {{display:block;margin-top:.18rem;color:var(--pp-ink);font-size:.85rem;}}
        .pp-v223-panel-head a {{color:var(--pp-orange);font-size:.60rem;font-weight:740;text-decoration:none;white-space:nowrap;}}

        .pp-v223-prediction-grid {{display:grid;grid-template-columns:repeat(5,1fr);gap:.45rem;}}
        .pp-v223-prediction {{display:block;padding:.58rem .58rem .54rem;color:var(--pp-ink);text-decoration:none;border-radius:12px;background:rgba(247,243,236,.78);border:1px solid rgba(16,38,61,.06);}}
        .pp-v223-prediction span {{display:block;color:var(--pp-text-muted);font-size:.56rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;}}
        .pp-v223-prediction strong {{display:block;margin-top:.20rem;color:var(--pp-ink);font-size:1rem;font-weight:850;letter-spacing:-.025em;}}
        .pp-v223-prediction:hover {{border-color:rgba(240,90,40,.30);transform:translateY(-1px);}}

        .pp-v223-environment {{background:linear-gradient(135deg,rgba(16,38,61,.025),rgba(255,255,255,.88));}}
        .pp-v223-env-grid {{display:grid;grid-template-columns:repeat(4,1fr);gap:.44rem;}}
        .pp-v223-env-chip {{display:flex;align-items:center;justify-content:space-between;gap:.5rem;padding:.52rem .60rem;color:var(--pp-ink);text-decoration:none;border:1px solid rgba(16,38,61,.065);border-radius:11px;background:rgba(255,255,255,.78);}}
        .pp-v223-env-chip span {{color:var(--pp-text-secondary);font-size:.63rem;font-weight:700;}}
        .pp-v223-env-chip strong {{color:var(--pp-orange);font-size:.74rem;font-weight:840;}}

        .pp-v223-bottom-grid {{display:grid;grid-template-columns:1fr 1fr;gap:.58rem;}}
        .pp-v223-compact {{display:block;min-height:70px;padding:.64rem .76rem;color:var(--pp-ink);text-decoration:none;border:1px solid var(--pp-line);border-radius:13px;background:rgba(255,255,255,.80);}}
        .pp-v223-compact strong {{display:block;margin-top:.22rem;color:var(--pp-ink);font-size:.73rem;line-height:1.24;}}
        .pp-v223-compact small {{display:block;margin-top:.28rem;color:var(--pp-orange);font-size:.58rem;font-weight:720;}}
        .pp-v223-empty {{color:var(--pp-text-muted);font-size:.68rem;padding:.45rem 0;}}

        .pp-athlete-card {{position:relative;width:100%;max-width:420px;margin-left:auto;overflow:hidden;color:#fff;border:1px solid rgba(240,90,40,.54);border-radius:25px;background:#10263D;box-shadow:0 20px 46px rgba(16,38,61,.20);}}
        .pp-athlete-visual {{position:relative;min-height:268px;overflow:hidden;border-bottom:1px solid rgba(255,255,255,.13);background:radial-gradient(circle at 18% 0%,rgba(255,255,255,.055),transparent 34%),#10263D;}}
        .pp-athlete-contours {{position:absolute;inset:0;opacity:.14;background:repeating-radial-gradient(ellipse at 91% 17%,transparent 0 19px,rgba(240,90,40,.70) 20px 21px,transparent 22px 37px);}}
        .pp-athlete-road {{position:absolute;left:-10%;right:-7%;bottom:27px;height:66px;transform:rotate(-6deg);opacity:.98;background:linear-gradient(164deg,transparent 0 47%,#F05A28 48% 53%,transparent 54%);}}
        .pp-athlete-photo {{position:absolute;right:-9%;bottom:-2%;width:80%;height:106%;object-fit:cover;object-position:54% 29%;filter:saturate(.92) contrast(1.04);-webkit-mask-image:radial-gradient(ellipse 72% 94% at 69% 57%,black 0 58%,rgba(0,0,0,.98) 66%,rgba(0,0,0,.78) 73%,rgba(0,0,0,.28) 83%,transparent 94%);mask-image:radial-gradient(ellipse 72% 94% at 69% 57%,black 0 58%,rgba(0,0,0,.98) 66%,rgba(0,0,0,.78) 73%,rgba(0,0,0,.28) 83%,transparent 94%);}}
        .pp-athlete-score-link {{position:absolute;z-index:7;left:16px;top:14px;text-decoration:none;}}
        .pp-athlete-score {{min-width:106px;padding:.58rem .76rem .53rem;border-radius:17px;background:rgba(7,24,41,.84);backdrop-filter:blur(9px);border:1px solid rgba(255,255,255,.10);}}
        .pp-athlete-score strong {{display:block;color:#F3C76C;font-size:3.75rem;font-weight:880;line-height:.86;letter-spacing:-.075em;}}
        .pp-athlete-score span {{display:block;margin-top:.28rem;color:#F3C76C;font-size:.64rem;font-weight:840;letter-spacing:.11em;}}
        .pp-athlete-identity {{position:absolute;z-index:5;left:17px;bottom:17px;max-width:52%;}}
        .pp-athlete-identity strong {{display:block;color:#fff;font-size:1.15rem;font-weight:840;}}
        .pp-athlete-identity span {{display:block;margin-top:.18rem;color:rgba(255,255,255,.65);font-size:.66rem;font-weight:670;letter-spacing:.055em;}}
        .pp-athlete-attributes {{display:grid;grid-template-columns:1fr 1fr;padding:.62rem .92rem .46rem;}}
        .pp-athlete-attribute {{display:flex;align-items:center;justify-content:space-between;gap:.65rem;padding:.58rem .36rem;color:#fff;border-bottom:1px solid rgba(255,255,255,.10);text-decoration:none;}}
        .pp-athlete-attribute:nth-child(odd) {{margin-right:.48rem;}}
        .pp-athlete-attribute:nth-child(even) {{margin-left:.48rem;}}
        .pp-athlete-attribute span {{color:rgba(255,255,255,.62);font-size:.74rem;font-weight:800;letter-spacing:.08em;}}
        .pp-athlete-attribute strong {{color:#fff;font-size:1.52rem;font-weight:870;letter-spacing:-.03em;}}
        .pp-athlete-attribute:hover strong,.pp-athlete-attribute:hover span {{color:var(--pp-orange);}}
        .pp-athlete-progress {{display:grid;grid-template-columns:1fr auto;gap:.08rem .75rem;padding:.70rem 1.08rem .86rem;color:#fff;text-decoration:none;}}
        .pp-athlete-progress span {{align-self:end;color:rgba(255,255,255,.59);font-size:.64rem;font-weight:820;letter-spacing:.09em;}}
        .pp-athlete-progress strong {{grid-row:1 / span 2;grid-column:2;align-self:center;color:#fff;font-size:2.05rem;font-weight:880;letter-spacing:-.05em;}}
        .pp-athlete-progress strong.positive {{color:#62C98A;}}
        .pp-athlete-progress small {{color:rgba(255,255,255,.50);font-size:.60rem;}}

        @media (min-width:1100px) {{
            [data-testid="stMainBlockContainer"] {{max-width:1450px;padding-left:2rem!important;padding-right:2rem!important;}}
        }}
        @media (max-width:1050px) {{
            .pp-v223-home-grid {{grid-template-columns:minmax(0,1fr) minmax(310px,.72fr);gap:1rem;}}
            .pp-v223-upnext-row {{grid-template-columns:1fr;}}
            .pp-v223-prediction strong {{font-size:.90rem;}}
        }}
        @media (max-width:820px) {{
            .pp-v223-home-grid {{grid-template-columns:1fr;}}
            .pp-v223-athlete-column {{grid-row:1;position:static;}}
            .pp-athlete-card {{max-width:430px;margin:0 auto .2rem;}}
            .pp-v22-week {{grid-template-columns:repeat(7,minmax(84px,1fr));overflow-x:auto;scrollbar-width:none;padding-bottom:.12rem;}}
            .pp-v22-week::-webkit-scrollbar {{display:none;}}
            .pp-v223-prediction-grid {{grid-template-columns:repeat(5,minmax(100px,1fr));overflow-x:auto;scrollbar-width:none;}}
            .pp-v223-env-grid {{grid-template-columns:repeat(4,minmax(100px,1fr));overflow-x:auto;scrollbar-width:none;}}
        }}
        @media (max-width:560px) {{
            .pp-v223-bottom-grid {{grid-template-columns:1fr;}}
            .pp-v223-upnext-row {{grid-template-columns:1fr;}}
            .pp-athlete-card {{max-width:100%;border-radius:20px;}}
            .pp-athlete-visual {{min-height:245px;}}
            .pp-athlete-score strong {{font-size:3.25rem;}}
            .pp-athlete-attribute strong {{font-size:1.30rem;}}
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