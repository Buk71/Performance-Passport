import base64
from pathlib import Path

import streamlit as st

from config import APP_NAME, VERSION, VERSION_NAME

ROOT = Path(__file__).resolve().parents[1]

PRIMARY_NAVIGATION = ['Coach', 'Plan', 'Activities', 'Performance', 'Passport']
MORE_NAVIGATION = ['Journal', 'Next Run', 'Learning', 'Progress', 'Goals', 'Training Blocks', 'Hall of Fame', 'Athletes', 'Import', 'Diagnostics', 'Settings']


def _pathmark_data_uri():
    path = ROOT / 'assets' / 'brand' / 'pathmark.svg'
    return base64.b64encode(path.read_bytes()).decode('ascii') if path.exists() else ''


def show_sidebar():
    st.sidebar.markdown(f'''<div class="pp-brand"><img class="pp-brand-pathmark" src="data:image/svg+xml;base64,{_pathmark_data_uri()}" alt="Performance Passport"><div><div class="pp-brand-title">{APP_NAME}</div><div class="pp-v21-motto">Every run has something to give.</div></div></div>''', unsafe_allow_html=True)

    requested_page = st.session_state.pop('pp_navigation_request', None)
    query_page = str(st.query_params.get('pp_page', '')).strip()
    if query_page in PRIMARY_NAVIGATION:
        requested_page = query_page
    if requested_page in PRIMARY_NAVIGATION and requested_page != st.session_state.get('primary_navigation'):
        st.session_state['primary_navigation'] = requested_page

    st.sidebar.markdown('<div class="pp-sidebar-section">Performance Passport</div>', unsafe_allow_html=True)
    primary_page = st.sidebar.radio('Primary navigation', PRIMARY_NAVIGATION, key='primary_navigation')
    st.sidebar.divider()
    st.sidebar.markdown('<div class="pp-sidebar-section">More</div>', unsafe_allow_html=True)
    more_page = st.sidebar.selectbox('More', ['None', *MORE_NAVIGATION], index=0, key='more_navigation', label_visibility='collapsed')
    page = more_page if more_page != 'None' else primary_page
    st.sidebar.markdown(f'''<div class="pp-sidebar-footer"><div class="pp-sidebar-footer-label">Current release</div><div class="pp-sidebar-footer-title">{VERSION_NAME}</div><div class="pp-sidebar-footer-meta">Version {VERSION}</div></div>''', unsafe_allow_html=True)
    return page
