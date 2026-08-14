"""Branded product entry for Performance Passport.

The welcome screen is deliberately separate from authentication. It introduces
the product without exposing athlete data, then hands control to the existing
single-page routing contract for the remainder of the browser session.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import Any, MutableMapping

import streamlit as st


WELCOME_SESSION_KEY = "pp_product_entered"
ROOT = Path(__file__).resolve().parent.parent
LOGO_PATH = ROOT / "assets" / "brand" / "pp_logo.png"


@lru_cache(maxsize=1)
def welcome_logo_data_uri() -> str:
    if not LOGO_PATH.exists():
        return ""
    encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _query_value(query_params: Any, key: str) -> str | None:
    try:
        value = query_params.get(key)
    except (AttributeError, KeyError):
        return None
    if isinstance(value, (tuple, list)):
        value = value[0] if value else None
    return str(value) if value is not None else None


def product_entry_granted(
    session_state: MutableMapping[str, Any],
    query_params: Any,
) -> bool:
    """Consume entry/deep-link intent and return whether the app may open."""
    if bool(session_state.get(WELCOME_SESSION_KEY)):
        return True

    direct_product_link = _query_value(query_params, "pp_page") is not None
    enter_requested = _query_value(query_params, "pp_enter") == "1"
    if not (direct_product_link or enter_requested):
        return False

    session_state[WELCOME_SESSION_KEY] = True
    if enter_requested:
        try:
            del query_params["pp_enter"]
        except (KeyError, TypeError, AttributeError):
            pass
    return True


def build_welcome_page_html() -> str:
    logo_uri = welcome_logo_data_uri()
    logo = (
        f'<img src="{logo_uri}" alt="Performance Passport Pathmark">'
        if logo_uri
        else '<strong class="pp-welcome-logo-fallback">PP</strong>'
    )
    return f"""
    <div class="pp-welcome-shell">
      <div class="pp-welcome-contours" aria-hidden="true"></div>
      <header class="pp-welcome-header">
        <div class="pp-welcome-brand">
          <div class="pp-welcome-logo">{logo}</div>
          <div><strong>Performance Passport</strong><span>Personal running intelligence</span></div>
        </div>
        <div class="pp-welcome-preview">PRODUCT PREVIEW</div>
      </header>

      <main class="pp-welcome-hero">
        <section class="pp-welcome-copy">
          <div class="pp-welcome-eyebrow"><i></i> THE ATHLETE, UNDERSTOOD</div>
          <h1>Every run has<br><em>something to give.</em></h1>
          <p class="pp-welcome-lead">Performance Passport turns training history into personal evidence—so every run can be understood, every decision can be explained and every goal can have a deliberate path.</p>
          <div class="pp-welcome-promises">
            <span>Understand what happened</span>
            <span>Decide what comes next</span>
            <span>Build around real life</span>
          </div>
          <a class="pp-welcome-enter" href="?pp_enter=1" target="_self" aria-label="Open Performance Passport">
            <span>Open Performance Passport</span><b aria-hidden="true">→</b>
          </a>
          <small class="pp-welcome-access">Development release · login will follow when the product is ready for hosted athlete access</small>
        </section>

        <section class="pp-welcome-stage" aria-label="Performance Passport product preview">
          <div class="pp-welcome-stage-glow"></div>
          <article class="pp-welcome-passport">
            <div class="pp-welcome-card-head"><span>ATHLETE PASSPORT</span><i>CURRENT</i></div>
            <h2>One athlete.<br>One connected story.</h2>
            <p>History, conditions, purpose and progression stay connected rather than becoming isolated statistics.</p>
            <div class="pp-welcome-signal-grid">
              <div><small>CAPABILITY</small><strong>Known</strong><span>from real evidence</span></div>
              <div><small>DIRECTION</small><strong>Planned</strong><span>with athlete control</span></div>
              <div><small>RACE DAY</small><strong>Explained</strong><span>in real conditions</span></div>
            </div>
          </article>
          <svg class="pp-welcome-route" viewBox="0 0 540 170" role="img" aria-label="A route connecting training evidence to future performance">
            <path class="pp-route-shadow" d="M20 138 C115 135 106 50 206 73 S346 151 520 31" />
            <path class="pp-route-line" d="M20 138 C115 135 106 50 206 73 S346 151 520 31" />
            <circle cx="20" cy="138" r="8"/><circle cx="206" cy="73" r="8"/><circle cx="520" cy="31" r="9"/>
          </svg>
          <div class="pp-welcome-mini-cards">
            <article><small>LATEST RUN</small><strong>Purpose recognised</strong><span>Evidence, not just pace</span></article>
            <article><small>TRAINING BLOCK</small><strong>Direction shaped</strong><span>History before template</span></article>
            <article><small>FUEL PLANNER</small><strong>Recovery supported</strong><span>Choices become a list</span></article>
          </div>
        </section>
      </main>

      <section class="pp-welcome-pillars" aria-label="Performance Passport principles">
        <article><span>01</span><div><small>UNDERSTAND</small><strong>How good was this run, really?</strong><p>Compare like with like and keep conditions, purpose and reliability visible.</p></div></article>
        <article><span>02</span><div><small>PLAN</small><strong>What should this athlete do next?</strong><p>Build from demonstrated rhythm, personal goals and the life around the training.</p></div></article>
        <article><span>03</span><div><small>ADAPT</small><strong>What changed—and who decides?</strong><p>Respond to real execution without silently rewriting the athlete's commitment.</p></div></article>
      </section>

      <footer class="pp-welcome-footer"><span>TRAIN · ANALYSE · IMPROVE</span><p>Performance Passport</p></footer>
    </div>
    <style>
      [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stSidebarCollapseButton"]{{display:none!important}}
      [data-testid="stHeader"]{{background:transparent!important}}
      [data-testid="stMain"]{{background:#F4F0E9!important}}
      [data-testid="stMainBlockContainer"]{{max-width:none!important;padding:0!important}}
      .pp-welcome-shell{{position:relative;isolation:isolate;min-height:100vh;overflow:hidden;padding:26px clamp(24px,4.5vw,78px) 30px;background:radial-gradient(circle at 86% 17%,rgba(240,90,40,.16),transparent 20%),radial-gradient(circle at 72% 34%,rgba(62,142,114,.11),transparent 26%),linear-gradient(135deg,#F8F5EF 0%,#F1ECE3 58%,#EAE4D9 100%);color:#10263D;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
      .pp-welcome-shell:before{{content:"";position:absolute;z-index:-1;inset:0;background:linear-gradient(90deg,rgba(16,38,61,.035) 1px,transparent 1px),linear-gradient(rgba(16,38,61,.025) 1px,transparent 1px);background-size:72px 72px;mask-image:linear-gradient(90deg,transparent,black 42%,black 100%);opacity:.55}}
      .pp-welcome-contours{{position:absolute;z-index:-1;width:760px;height:760px;right:-230px;top:-260px;border:1px solid rgba(16,38,61,.08);border-radius:42% 58% 55% 45%;transform:rotate(18deg);box-shadow:0 0 0 36px rgba(16,38,61,.026),0 0 0 78px rgba(16,38,61,.02),0 0 0 126px rgba(16,38,61,.016)}}
      .pp-welcome-header{{max-width:1480px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;gap:20px;position:relative;z-index:2}} .pp-welcome-brand{{display:flex;align-items:center;gap:12px}} .pp-welcome-logo{{width:76px;height:55px;display:flex;align-items:center;justify-content:center;overflow:hidden}} .pp-welcome-logo img{{width:94px;height:64px;object-fit:contain;filter:drop-shadow(0 5px 8px rgba(240,90,40,.18))}} .pp-welcome-logo-fallback{{font-size:25px;color:#10263D}} .pp-welcome-brand>div:last-child{{display:flex;flex-direction:column}} .pp-welcome-brand strong{{font-size:15px;letter-spacing:-.01em}} .pp-welcome-brand span{{margin-top:2px;color:#647687;font-size:10px;font-weight:700;letter-spacing:.065em;text-transform:uppercase}} .pp-welcome-preview{{padding:8px 11px;border:1px solid rgba(16,38,61,.12);border-radius:999px;background:rgba(255,255,255,.48);font-size:9px;font-weight:850;letter-spacing:.14em;color:#657687}}
      .pp-welcome-hero{{max-width:1480px;margin:clamp(45px,7vh,96px) auto 42px;display:grid;grid-template-columns:minmax(340px,.84fr) minmax(520px,1.16fr);gap:clamp(48px,7vw,110px);align-items:center}} .pp-welcome-copy{{position:relative;z-index:2}} .pp-welcome-eyebrow{{display:flex;align-items:center;gap:10px;color:#53687B;font-size:11px;font-weight:850;letter-spacing:.17em}} .pp-welcome-eyebrow i{{display:block;width:29px;height:3px;border-radius:99px;background:#F05A28;box-shadow:0 0 12px rgba(240,90,40,.36)}} .pp-welcome-copy h1{{margin:18px 0 20px!important;color:#10263D!important;font-size:clamp(52px,6vw,90px)!important;font-weight:790!important;line-height:.96!important;letter-spacing:-.065em!important}} .pp-welcome-copy h1 em{{color:#F05A28;font-style:normal;font-weight:790}} .pp-welcome-lead{{max-width:650px;color:#52677A!important;font-size:clamp(16px,1.4vw,20px)!important;line-height:1.62!important}} .pp-welcome-promises{{display:flex;flex-wrap:wrap;gap:9px;margin:25px 0 27px}} .pp-welcome-promises span{{padding:8px 11px;border:1px solid rgba(16,38,61,.11);border-radius:999px;background:rgba(255,255,255,.58);color:#344F67;font-size:11px;font-weight:720}} .pp-welcome-enter{{display:inline-flex;align-items:center;justify-content:space-between;gap:30px;min-width:290px;padding:15px 17px 15px 20px;border-radius:13px;background:#10263D;color:#fff!important;text-decoration:none!important;font-size:14px;font-weight:780;box-shadow:0 12px 28px rgba(16,38,61,.22);transition:transform .16s ease,box-shadow .16s ease,background .16s ease}} .pp-welcome-enter b{{display:grid;place-items:center;width:30px;height:30px;border-radius:9px;background:#F05A28;font-size:18px}} .pp-welcome-enter:hover{{background:#173A59;transform:translateY(-2px);box-shadow:0 15px 34px rgba(16,38,61,.26)}} .pp-welcome-enter:focus-visible{{outline:3px solid #F05A28;outline-offset:4px}} .pp-welcome-access{{display:block;max-width:420px;margin-top:13px;color:#758493;font-size:10px;line-height:1.5}}
      .pp-welcome-stage{{position:relative;min-height:520px}} .pp-welcome-stage-glow{{position:absolute;inset:5% 3% 12% 10%;background:radial-gradient(circle,rgba(240,90,40,.20),rgba(62,142,114,.08) 42%,transparent 70%);filter:blur(20px)}} .pp-welcome-passport{{position:relative;z-index:2;width:min(92%,650px);margin-left:auto;padding:25px 26px 27px;border:1px solid rgba(255,255,255,.8);border-radius:24px;background:linear-gradient(145deg,rgba(255,255,255,.96),rgba(247,243,236,.91));box-shadow:0 28px 60px rgba(16,38,61,.16),inset 0 1px 0 #fff;transform:rotate(1deg)}} .pp-welcome-card-head{{display:flex;justify-content:space-between;align-items:center}} .pp-welcome-card-head span,.pp-welcome-passport small,.pp-welcome-mini-cards small{{font-size:9px;font-weight:880;letter-spacing:.16em;color:#718091}} .pp-welcome-card-head i{{padding:6px 8px;border-radius:999px;background:#E7F3ED;color:#3E8E72;font-size:8px;font-style:normal;font-weight:880;letter-spacing:.1em}} .pp-welcome-passport h2{{margin:15px 0 10px!important;color:#10263D!important;font-size:clamp(28px,3vw,43px)!important;line-height:1.02!important;letter-spacing:-.045em!important}} .pp-welcome-passport>p{{max-width:520px;color:#647687!important;font-size:12px!important;line-height:1.6!important}} .pp-welcome-signal-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:20px}} .pp-welcome-signal-grid>div{{padding:13px;border:1px solid #E8E1D7;border-radius:13px;background:#F7F3EC}} .pp-welcome-signal-grid strong{{display:block;margin:6px 0 3px;font-size:20px}} .pp-welcome-signal-grid span{{font-size:9px;color:#718091}}
      .pp-welcome-route{{position:relative;z-index:3;display:block;width:min(86%,590px);height:145px;margin:-5px 0 -18px auto;overflow:visible}} .pp-welcome-route path,.pp-welcome-route circle{{fill:none;stroke-linecap:round}} .pp-route-shadow{{stroke:rgba(240,90,40,.22);stroke-width:18;filter:blur(6px)}} .pp-route-line{{stroke:#F05A28;stroke-width:5;stroke-dasharray:12 12;animation:pp-route-flow 10s linear infinite}} .pp-welcome-route circle{{fill:#F7F3EC;stroke:#10263D;stroke-width:4}} .pp-welcome-route circle:last-child{{fill:#F05A28;stroke:#F05A28}}
      .pp-welcome-mini-cards{{position:relative;z-index:2;display:grid;grid-template-columns:repeat(3,1fr);gap:10px;width:96%;margin-left:auto}} .pp-welcome-mini-cards article{{min-height:94px;padding:14px;border:1px solid rgba(16,38,61,.09);border-radius:14px;background:rgba(255,255,255,.84);box-shadow:0 10px 23px rgba(16,38,61,.08)}} .pp-welcome-mini-cards strong{{display:block;margin:7px 0 4px;color:#10263D;font-size:12px}} .pp-welcome-mini-cards span{{color:#718091;font-size:9px}}
      .pp-welcome-pillars{{max-width:1480px;margin:0 auto;display:grid;grid-template-columns:repeat(3,1fr);gap:12px;border-top:1px solid rgba(16,38,61,.11);padding-top:20px}} .pp-welcome-pillars article{{display:flex;gap:15px;padding:15px 16px;border-radius:14px;transition:background .15s ease,transform .15s ease}} .pp-welcome-pillars article:hover{{background:rgba(255,255,255,.55);transform:translateY(-2px)}} .pp-welcome-pillars article>span{{display:grid;place-items:center;flex:0 0 34px;width:34px;height:34px;border-radius:10px;background:#10263D;color:#fff;font-size:10px;font-weight:850}} .pp-welcome-pillars small{{display:block;color:#F05A28;font-size:9px;font-weight:880;letter-spacing:.16em}} .pp-welcome-pillars strong{{display:block;margin:5px 0;color:#10263D;font-size:13px}} .pp-welcome-pillars p{{margin:0;color:#6A7A89!important;font-size:10px!important;line-height:1.55!important}} .pp-welcome-footer{{max-width:1480px;margin:24px auto 0;display:flex;justify-content:space-between;border-top:1px solid rgba(16,38,61,.08);padding-top:15px;color:#82909D;font-size:9px;font-weight:800;letter-spacing:.15em}} .pp-welcome-footer p{{margin:0!important;color:#82909D!important;font-size:9px!important}}
      @keyframes pp-route-flow{{to{{stroke-dashoffset:-120}}}} @media(prefers-reduced-motion:reduce){{.pp-route-line{{animation:none}}.pp-welcome-enter,.pp-welcome-pillars article{{transition:none}}}}
      @media(max-width:1050px){{.pp-welcome-hero{{grid-template-columns:1fr;margin-top:55px}}.pp-welcome-copy{{max-width:790px}}.pp-welcome-stage{{min-height:auto}}.pp-welcome-passport{{margin:0 auto;width:94%}}.pp-welcome-mini-cards{{width:94%;margin:0 auto}}}}
      @media(max-width:680px){{.pp-welcome-shell{{padding:18px 17px 24px}}.pp-welcome-preview{{display:none}}.pp-welcome-brand span{{font-size:8px}}.pp-welcome-hero{{margin-top:45px;gap:42px}}.pp-welcome-copy h1{{font-size:clamp(43px,14vw,64px)!important}}.pp-welcome-lead{{font-size:15px!important}}.pp-welcome-enter{{width:100%;min-width:0}}.pp-welcome-passport{{padding:20px 18px;transform:none}}.pp-welcome-signal-grid{{grid-template-columns:1fr}}.pp-welcome-route{{width:100%;height:115px}}.pp-welcome-mini-cards,.pp-welcome-pillars{{grid-template-columns:1fr}}.pp-welcome-mini-cards{{width:100%}}.pp-welcome-pillars article{{padding:12px 6px}}}}
    </style>
    """


def show_welcome_page() -> None:
    st.html(build_welcome_page_html())
