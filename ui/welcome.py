"""Branded product entry for Performance Passport.

The welcome screen is deliberately separate from authentication. It introduces
the product without exposing athlete data, then hands control to the existing
single-page routing contract for the remainder of the browser session.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Any, MutableMapping, Sequence
from urllib.parse import urlencode

import streamlit as st

from ui.athlete_selection import SESSION_ID_KEY, get_athletes


WELCOME_SESSION_KEY = "pp_product_entered"
ROOT = Path(__file__).resolve().parent.parent
LOGO_PATH = ROOT / "assets" / "brand" / "pp_logo.png"
RUNNER_PATH = ROOT / "assets" / "brand" / "home_kit_runner.png"


@lru_cache(maxsize=1)
def welcome_logo_data_uri() -> str:
    if not LOGO_PATH.exists():
        return ""
    encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@lru_cache(maxsize=1)
def welcome_runner_data_uri() -> str:
    if not RUNNER_PATH.exists():
        return ""
    encoded = base64.b64encode(RUNNER_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _query_value(query_params: Any, key: str) -> str | None:
    try:
        value = query_params.get(key)
    except (AttributeError, KeyError):
        return None
    if isinstance(value, (tuple, list)):
        value = value[0] if value else None
    return str(value) if value is not None else None


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _athlete_name(row: Sequence[Any]) -> str:
    return f"{row[1] or ''} {row[2] or ''}".strip()


def _athlete_entry_markup(athletes: Sequence[Sequence[Any]]) -> str:
    choices = []
    for row in athletes:
        athlete_id = _positive_int(row[0] if row else None)
        name = _athlete_name(row) if len(row) >= 3 else ""
        if athlete_id is None or not name:
            continue
        initials = "".join(part[0] for part in name.split() if part)[:2].upper()
        href = escape(
            f"?{urlencode({'pp_enter': 1, 'pp_athlete': athlete_id})}",
            quote=True,
        )
        choices.append(
            f"""
            <a href="{href}" target="_self" aria-label="Open {escape(name)}'s Performance Passport">
              <span class="pp-athlete-initials">{escape(initials)}</span>
              <span><small>ATHLETE PASSPORT</small><strong>{escape(name)}</strong></span>
              <b aria-hidden="true">→</b>
            </a>
            """
        )

    if not choices:
        return """
          <a class="pp-welcome-enter" href="?pp_enter=1" target="_self" aria-label="Open Performance Passport">
            <span>Open Performance Passport</span><b aria-hidden="true">→</b>
          </a>
        """

    return f"""
      <div id="athlete-entry" class="pp-athlete-entry">
        <div class="pp-athlete-entry-label">CHOOSE YOUR PASSPORT</div>
        <div class="pp-athlete-choices">{''.join(choices)}</div>
      </div>
    """


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
        requested_athlete_id = _positive_int(
            _query_value(query_params, "pp_athlete")
        )
        if requested_athlete_id is not None:
            session_state[SESSION_ID_KEY] = requested_athlete_id
            session_state.pop("selected_athlete_name", None)
        try:
            del query_params["pp_enter"]
        except (KeyError, TypeError, AttributeError):
            pass
        try:
            del query_params["pp_athlete"]
        except (KeyError, TypeError, AttributeError):
            pass
    return True


def build_welcome_page_html(
    athletes: Sequence[Sequence[Any]] = (),
) -> str:
    logo_uri = welcome_logo_data_uri()
    logo = (
        f'<img src="{logo_uri}" alt="Performance Passport Pathmark">'
        if logo_uri
        else '<strong class="pp-welcome-logo-fallback">PP</strong>'
    )
    runner_uri = welcome_runner_data_uri()
    runner = (
        f'<img class="pp-welcome-runner" src="{runner_uri}" alt="" '
        'aria-hidden="true">'
        if runner_uri
        else ""
    )
    athlete_entry = _athlete_entry_markup(athletes)
    closing_href = "#athlete-entry" if athletes else "?pp_enter=1"
    closing_label = "Choose athlete to enter" if athletes else "Enter Performance Passport"
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
          <p class="pp-welcome-lead">Performance Passport turns a lifetime of training into personal evidence—so the athlete can understand what happened, know what comes next and build towards a goal with purpose.</p>
          <div class="pp-welcome-promises">
            <span>Personal, not generic</span>
            <span>Evidence, not mystery</span>
            <span>Direction, not noise</span>
          </div>
          {athlete_entry}
          <small class="pp-welcome-access">Development release · login will follow when the product is ready for hosted athlete access</small>
        </section>

        <section class="pp-welcome-stage" aria-label="Performance Passport product preview">
          <div class="pp-welcome-stage-glow"></div>
          <div class="pp-welcome-stage-top">
            <article class="pp-welcome-passport">
              <div class="pp-welcome-card-head"><span>ATHLETE PASSPORT</span><i>LIVE PROFILE</i></div>
              <h2>One athlete.<br>One connected story.</h2>
              <p>History, conditions, purpose and progression stay connected rather than becoming isolated statistics.</p>
              <div class="pp-welcome-signal-grid">
                <div><small>CAPABILITY</small><strong>Known</strong><span>from real evidence</span></div>
                <div><small>DIRECTION</small><strong>Shaped</strong><span>around the athlete</span></div>
                <div><small>RACE DAY</small><strong>Explained</strong><span>in real conditions</span></div>
              </div>
            </article>
            <div class="pp-welcome-runner-frame" aria-hidden="true">{runner}</div>
          </div>
          <svg class="pp-welcome-route" viewBox="0 0 540 170" role="img" aria-label="A route connecting training evidence to future performance">
            <path class="pp-route-shadow" d="M20 138 C115 135 106 50 206 73 S346 151 520 31" />
            <path class="pp-route-line" d="M20 138 C115 135 106 50 206 73 S346 151 520 31" />
            <circle cx="20" cy="138" r="8"/><circle cx="206" cy="73" r="8"/><circle cx="520" cy="31" r="9"/>
          </svg>
          <div class="pp-welcome-mini-cards">
            <article><small>LATEST RUN</small><strong>Purpose recognised</strong><span>Evidence, not just pace</span></article>
            <article><small>NEXT RUN</small><strong>Direction made clear</strong><span>One useful decision</span></article>
            <article><small>FUEL PLANNER</small><strong>Recovery supported</strong><span>Choices become a list</span></article>
          </div>
        </section>
      </main>

      <section class="pp-welcome-pillars" aria-label="Performance Passport principles">
        <article><span>01</span><div><small>UNDERSTAND</small><strong>How good was this run, really?</strong><p>Compare like with like and keep conditions, purpose and reliability visible.</p></div></article>
        <article><span>02</span><div><small>PLAN</small><strong>What should this athlete do next?</strong><p>Build from demonstrated rhythm, personal goals and the life around the training.</p></div></article>
        <article><span>03</span><div><small>ADAPT</small><strong>What changed—and who decides?</strong><p>Respond to real execution without silently rewriting the athlete's commitment.</p></div></article>
      </section>

      <section class="pp-welcome-product-intro">
        <div class="pp-product-kicker">A DIFFERENT KIND OF RUNNING PLATFORM</div>
        <div class="pp-product-intro-grid">
          <h2>Not another activity log.<br><em>A performance intelligence layer.</em></h2>
          <div>
            <p>Most platforms tell an athlete what they did. Performance Passport is designed to explain what it meant in the context of their own history—and turn that understanding into the next deliberate action.</p>
            <p class="pp-evidence-note"><i></i>Deterministic evidence creates the conclusion. Confidence, source and limitations remain visible.</p>
          </div>
        </div>
      </section>

      <section class="pp-welcome-features" aria-label="Special Performance Passport capabilities">
        <article class="pp-feature pp-feature-dark pp-feature-wide">
          <span class="pp-feature-number">01</span><small>THE LIVING PASSPORT</small>
          <h3>A profile that learns the athlete—not just their PBs.</h3>
          <p>Capability, pace and heart-rate anchors, training rhythm, environmental response, workout associations and factual achievements become one evolving performance identity.</p>
          <div class="pp-feature-tags"><span>Personal anchors</span><span>Training DNA</span><span>Evidence confidence</span></div>
        </article>
        <article class="pp-feature pp-feature-orange">
          <span class="pp-feature-number">02</span><small>TRUE RUN QUALITY</small>
          <h3>How good was this run, really?</h3>
          <p>Session purpose, comparable-run ranking, pace reliability, stopped time and continuity help separate genuine progress from a flattering headline number.</p>
        </article>
        <article class="pp-feature">
          <span class="pp-feature-number">03</span><small>CONDITIONS IN CONTEXT</small>
          <h3>The weather and the road do not disappear.</h3>
          <p>Heat, humidity, hills, wind and trail effects inform the interpretation while factual results and PBs remain untouched.</p>
          <div class="pp-condition-row"><span>HEAT</span><span>HILLS</span><span>WIND</span><span>TRAIL</span></div>
        </article>
        <article class="pp-feature">
          <span class="pp-feature-number">04</span><small>BEST RUNS, REDEFINED</small>
          <h3>More than the fastest day.</h3>
          <p>Best Ever and Hall of Fame recognition can celebrate an exceptional easy run, long run or quality session—not only races and personal bests.</p>
        </article>
        <article class="pp-feature pp-feature-race pp-feature-wide">
          <span class="pp-feature-number">05</span><small>RACE INTELLIGENCE</small>
          <h3>Capability → Ideal → Race Today</h3>
          <p>Forecasts separate underlying capability from ideal conditions and the likely reality of the selected course, weather, wind and surface. Goal likelihood changes; the athlete's underlying ability does not.</p>
          <div class="pp-race-track" aria-hidden="true"><i></i><i></i><i></i></div>
          <div class="pp-race-labels"><span>CAPABILITY</span><span>IDEAL</span><span>RACE TODAY</span></div>
        </article>
        <article class="pp-feature pp-feature-green">
          <span class="pp-feature-number">06</span><small>HISTORY-LED TRAINING BLOCKS</small>
          <h3>A plan earned by the evidence.</h3>
          <p>Frequency, reliable mileage, long-run pattern, quality rhythm, goals and real-life availability shape the block before any template is considered.</p>
        </article>
        <article class="pp-feature">
          <span class="pp-feature-number">07</span><small>DELIBERATE ADAPTATION</small>
          <h3>Plans can respond without taking control.</h3>
          <p>Planned and completed training remain side by side. A safer change is explained, and only an accepted decision changes what comes next.</p>
          <div class="pp-decision-row"><span>ACCEPT</span><span>DEFER</span><span>REJECT</span></div>
        </article>
        <article class="pp-feature pp-feature-fuel pp-feature-wide">
          <span class="pp-feature-number">08</span><small>TRAINING-AWARE FUEL PLANNER</small>
          <h3>Seven days of training become seven days of useful food choices.</h3>
          <p>Rest, easy, quality and long-run days each receive appropriate guidance, rotating meal options and one quantity-aware shopping list. Omnivore, pescatarian, vegetarian and vegan athletes remain independently supported.</p>
          <div class="pp-feature-tags pp-fuel-tags"><span>Daily choices</span><span>Recovery support</span><span>Household roll-up</span><span>Shopping CSV</span></div>
        </article>
      </section>

      <section class="pp-welcome-loop" aria-label="The weekly coaching loop">
        <div class="pp-product-kicker">ONE CONNECTED WEEK</div>
        <div class="pp-loop-heading"><h2>From evidence to action—and back again.</h2><p>Each part of the product strengthens the next rather than becoming another disconnected dashboard.</p></div>
        <div class="pp-loop-grid">
          <article><b>01</b><small>READ</small><strong>Understand the run</strong><p>Purpose, reliability, conditions and comparable evidence.</p></article>
          <article><b>02</b><small>LEARN</small><strong>Update the Passport</strong><p>Patterns become personal anchors and cautious associations.</p></article>
          <article><b>03</b><small>PLAN</small><strong>Shape the week</strong><p>Goals meet demonstrated rhythm and real availability.</p></article>
          <article><b>04</b><small>ADAPT</small><strong>Respond deliberately</strong><p>Execution informs the choice without rewriting history.</p></article>
          <article><b>05</b><small>SUPPORT</small><strong>Fuel the work</strong><p>Training demand becomes practical meals and shopping.</p></article>
        </div>
      </section>

      <section class="pp-welcome-trust">
        <div class="pp-trust-copy">
          <div class="pp-product-kicker">BUILT ON TRUST</div>
          <h2>Honest enough to say what it knows—and what it does not.</h2>
          <p>Performance Passport protects factual achievements, excludes unreliable evidence where necessary and shows the basis for coaching conclusions. Personal evidence leads; generic support is labelled.</p>
        </div>
        <div class="pp-trust-principles">
          <article><span>01</span><div><strong>Real athlete history</strong><p>Personal evidence before generic assumptions.</p></div></article>
          <article><span>02</span><div><strong>Transparent confidence</strong><p>Source and limitations remain part of the answer.</p></div></article>
          <article><span>03</span><div><strong>Protected athlete agency</strong><p>The plan changes only through a deliberate decision.</p></div></article>
        </div>
      </section>

      <section class="pp-welcome-roadmap">
        <div>
          <div class="pp-product-kicker">CONNECTED PRODUCT ROADMAP</div>
          <h2>The complete loop is getting closer.</h2>
          <p>Automatic activity delivery, watch-ready training and secure athlete–coach access are the next connected layers—not claims about the current development release.</p>
        </div>
        <div class="pp-roadmap-items">
          <article><small>NEXT</small><strong>Garmin-connected activities</strong><p>Watch → FIT evidence → fresh analysis.</p></article>
          <article><small>THEN</small><strong>Workouts back to the watch</strong><p>Approved sessions delivered where the athlete trains.</p></article>
          <article><small>COMMERCIAL PILOT</small><strong>Athlete and coach access</strong><p>Secure identities, permissions and durable cloud data.</p></article>
        </div>
      </section>

      <section class="pp-welcome-closing">
        <div class="pp-closing-mark">PP</div>
        <div><div class="pp-product-kicker">YOUR HISTORY. YOUR EVIDENCE. YOUR DIRECTION.</div><h2>See what every run has to give.</h2></div>
        <a class="pp-welcome-enter pp-welcome-enter-light" href="{closing_href}" target="_self"><span>{closing_label}</span><b aria-hidden="true">→</b></a>
      </section>

      <footer class="pp-welcome-footer"><span>TRAIN · ANALYSE · IMPROVE</span><p>Performance Passport</p></footer>
    </div>
    <style>
      [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stSidebarCollapseButton"]{{display:none!important}}
      [data-testid="stHeader"]{{display:none!important}}
      [data-testid="stMain"]{{background:#F4F0E9!important}}
      [data-testid="stMainBlockContainer"]{{max-width:none!important;padding:0!important}}
      .pp-welcome-shell{{position:relative;isolation:isolate;min-height:100vh;overflow:hidden;padding:26px clamp(24px,4.5vw,78px) 30px;background:radial-gradient(circle at 86% 17%,rgba(240,90,40,.16),transparent 20%),radial-gradient(circle at 72% 34%,rgba(62,142,114,.11),transparent 26%),linear-gradient(135deg,#F8F5EF 0%,#F1ECE3 58%,#EAE4D9 100%);color:#10263D;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
      .pp-welcome-shell:before{{content:"";position:absolute;z-index:-1;inset:0;background:linear-gradient(90deg,rgba(16,38,61,.035) 1px,transparent 1px),linear-gradient(rgba(16,38,61,.025) 1px,transparent 1px);background-size:72px 72px;mask-image:linear-gradient(90deg,transparent,black 42%,black 100%);opacity:.55}}
      .pp-welcome-contours{{position:absolute;z-index:-1;width:760px;height:760px;right:-230px;top:-260px;border:1px solid rgba(16,38,61,.08);border-radius:42% 58% 55% 45%;transform:rotate(18deg);box-shadow:0 0 0 36px rgba(16,38,61,.026),0 0 0 78px rgba(16,38,61,.02),0 0 0 126px rgba(16,38,61,.016)}}
      .pp-welcome-header{{max-width:1480px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;gap:20px;position:relative;z-index:2}} .pp-welcome-brand{{display:flex;align-items:center;gap:14px}} .pp-welcome-logo{{width:100px;height:70px;display:flex;align-items:center;justify-content:center;overflow:visible}} .pp-welcome-logo img{{width:122px;height:82px;object-fit:contain;filter:drop-shadow(0 5px 8px rgba(240,90,40,.18))}} .pp-welcome-logo-fallback{{font-size:29px;color:#10263D}} .pp-welcome-brand>div:last-child{{display:flex;flex-direction:column}} .pp-welcome-brand strong{{font-size:15px;letter-spacing:-.01em}} .pp-welcome-brand span{{margin-top:2px;color:#647687;font-size:10px;font-weight:700;letter-spacing:.065em;text-transform:uppercase}} .pp-welcome-preview{{padding:8px 11px;border:1px solid rgba(16,38,61,.12);border-radius:999px;background:rgba(255,255,255,.48);font-size:9px;font-weight:850;letter-spacing:.14em;color:#657687}}
      .pp-welcome-hero{{max-width:1480px;margin:clamp(45px,7vh,96px) auto 42px;display:grid;grid-template-columns:minmax(340px,.84fr) minmax(520px,1.16fr);gap:clamp(48px,7vw,110px);align-items:center}} .pp-welcome-copy{{position:relative;z-index:2}} .pp-welcome-eyebrow{{display:flex;align-items:center;gap:10px;color:#53687B;font-size:11px;font-weight:850;letter-spacing:.17em}} .pp-welcome-eyebrow i{{display:block;width:29px;height:3px;border-radius:99px;background:#F05A28;box-shadow:0 0 12px rgba(240,90,40,.36)}} .pp-welcome-copy h1{{margin:18px 0 20px!important;color:#10263D!important;font-size:clamp(52px,6vw,90px)!important;font-weight:790!important;line-height:.96!important;letter-spacing:-.065em!important}} .pp-welcome-copy h1 em{{color:#F05A28;font-style:normal;font-weight:790}} .pp-welcome-lead{{max-width:650px;color:#52677A!important;font-size:clamp(16px,1.4vw,20px)!important;line-height:1.62!important}} .pp-welcome-promises{{display:flex;flex-wrap:wrap;gap:9px;margin:25px 0 27px}} .pp-welcome-promises span{{padding:8px 11px;border:1px solid rgba(16,38,61,.11);border-radius:999px;background:rgba(255,255,255,.58);color:#344F67;font-size:11px;font-weight:720}} .pp-welcome-enter{{display:inline-flex;align-items:center;justify-content:space-between;gap:30px;min-width:290px;padding:15px 17px 15px 20px;border-radius:13px;background:#10263D;color:#fff!important;text-decoration:none!important;font-size:14px;font-weight:780;box-shadow:0 12px 28px rgba(16,38,61,.22);transition:transform .16s ease,box-shadow .16s ease,background .16s ease}} .pp-welcome-enter b{{display:grid;place-items:center;width:30px;height:30px;border-radius:9px;background:#F05A28;font-size:18px}} .pp-welcome-enter:hover{{background:#173A59;transform:translateY(-2px);box-shadow:0 15px 34px rgba(16,38,61,.26)}} .pp-welcome-enter:focus-visible{{outline:3px solid #F05A28;outline-offset:4px}} .pp-welcome-access{{display:block;max-width:420px;margin-top:13px;color:#758493;font-size:10px;line-height:1.5}}
      .pp-athlete-entry{{max-width:650px;margin:26px 0 0}} .pp-athlete-entry-label{{margin-bottom:9px;color:#647687;font-size:9px;font-weight:900;letter-spacing:.17em}} .pp-athlete-choices{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}} .pp-athlete-choices>a{{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:11px;min-height:68px;padding:10px 12px;border:1px solid rgba(16,38,61,.12);border-radius:14px;background:rgba(255,255,255,.76);color:#10263D!important;text-decoration:none!important;box-shadow:0 9px 22px rgba(16,38,61,.07);transition:transform .16s ease,box-shadow .16s ease,border-color .16s ease}} .pp-athlete-choices>a:hover{{transform:translateY(-2px);border-color:rgba(240,90,40,.48);box-shadow:0 13px 27px rgba(16,38,61,.11)}} .pp-athlete-choices>a:focus-visible{{outline:3px solid #F05A28;outline-offset:3px}} .pp-athlete-initials{{display:grid;place-items:center;width:39px;height:39px;border-radius:12px;background:#10263D;color:#fff;font-size:11px;font-weight:900;letter-spacing:.04em}} .pp-athlete-choices>a>span:nth-child(2){{display:flex;min-width:0;flex-direction:column}} .pp-athlete-choices small{{color:#718091;font-size:7px;font-weight:900;letter-spacing:.13em}} .pp-athlete-choices strong{{margin-top:4px;overflow:hidden;text-overflow:ellipsis;color:#10263D;font-size:12px;white-space:nowrap}} .pp-athlete-choices b{{display:grid;place-items:center;width:28px;height:28px;border-radius:9px;background:#F05A28;color:#fff;font-size:16px}}
      .pp-welcome-stage{{position:relative;min-height:520px}} .pp-welcome-stage-glow{{position:absolute;inset:5% 3% 12% 10%;background:radial-gradient(circle,rgba(240,90,40,.20),rgba(62,142,114,.08) 42%,transparent 70%);filter:blur(20px)}} .pp-welcome-passport{{position:relative;z-index:2;width:min(92%,650px);margin-left:auto;padding:25px 26px 27px;border:1px solid rgba(255,255,255,.8);border-radius:24px;background:linear-gradient(145deg,rgba(255,255,255,.96),rgba(247,243,236,.91));box-shadow:0 28px 60px rgba(16,38,61,.16),inset 0 1px 0 #fff;transform:none}} .pp-welcome-card-head{{display:flex;justify-content:space-between;align-items:center}} .pp-welcome-card-head span,.pp-welcome-passport small,.pp-welcome-mini-cards small{{font-size:9px;font-weight:880;letter-spacing:.16em;color:#718091}} .pp-welcome-card-head i{{padding:6px 8px;border-radius:999px;background:#E7F3ED;color:#3E8E72;font-size:8px;font-style:normal;font-weight:880;letter-spacing:.1em}} .pp-welcome-passport h2{{margin:15px 0 10px!important;color:#10263D!important;font-size:clamp(28px,3vw,43px)!important;line-height:1.02!important;letter-spacing:-.045em!important}} .pp-welcome-passport>p{{max-width:520px;color:#647687!important;font-size:12px!important;line-height:1.6!important}} .pp-welcome-signal-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:20px}} .pp-welcome-signal-grid>div{{padding:13px;border:1px solid #E8E1D7;border-radius:13px;background:#F7F3EC}} .pp-welcome-signal-grid strong{{display:block;margin:6px 0 3px;font-size:20px}} .pp-welcome-signal-grid span{{font-size:9px;color:#718091}}
      .pp-welcome-stage{{isolation:isolate;min-height:560px}} .pp-welcome-stage-glow{{z-index:0}} .pp-welcome-stage-top{{position:relative;z-index:2;display:grid;grid-template-columns:minmax(470px,1fr) minmax(180px,.36fr);gap:14px;align-items:stretch;min-height:330px}} .pp-welcome-passport{{width:100%;min-height:310px;margin:0;padding:25px 26px 27px;background:linear-gradient(145deg,rgba(255,255,255,.97),rgba(247,243,236,.92));backdrop-filter:blur(2px)}} .pp-welcome-runner-frame{{position:relative;align-self:stretch;min-width:0;overflow:hidden;border:1px solid rgba(255,255,255,.68);border-radius:24px;background:radial-gradient(circle at 48% 24%,rgba(240,90,40,.22),transparent 33%),linear-gradient(155deg,rgba(255,255,255,.58),rgba(234,228,217,.24));box-shadow:0 24px 52px rgba(16,38,61,.11),inset 0 1px 0 rgba(255,255,255,.72)}} .pp-welcome-runner-frame:before{{content:"";position:absolute;inset:12% -90% -75% -45%;border:1px solid rgba(16,38,61,.09);border-radius:48%;box-shadow:0 0 0 24px rgba(16,38,61,.028),0 0 0 55px rgba(16,38,61,.021),0 0 0 91px rgba(16,38,61,.016);transform:rotate(-15deg)}} .pp-welcome-runner{{position:absolute;z-index:2;right:-43px;bottom:-135px;width:auto;height:465px;object-fit:contain;filter:drop-shadow(0 24px 25px rgba(16,38,61,.23));pointer-events:none;user-select:none}} .pp-welcome-route{{z-index:4}} .pp-welcome-mini-cards{{z-index:4}}
      .pp-welcome-route{{position:relative;z-index:3;display:block;width:min(86%,590px);height:145px;margin:-5px 0 -18px auto;overflow:visible}} .pp-welcome-route path,.pp-welcome-route circle{{fill:none;stroke-linecap:round}} .pp-route-shadow{{stroke:rgba(240,90,40,.22);stroke-width:18;filter:blur(6px)}} .pp-route-line{{stroke:#F05A28;stroke-width:5;stroke-dasharray:12 12;animation:pp-route-flow 10s linear infinite}} .pp-welcome-route circle{{fill:#F7F3EC;stroke:#10263D;stroke-width:4}} .pp-welcome-route circle:last-child{{fill:#F05A28;stroke:#F05A28}}
      .pp-welcome-mini-cards{{position:relative;z-index:2;display:grid;grid-template-columns:repeat(3,1fr);gap:10px;width:96%;margin:18px 0 0 auto}} .pp-welcome-mini-cards article{{min-height:94px;padding:14px;border:1px solid rgba(16,38,61,.09);border-radius:14px;background:rgba(255,255,255,.84);box-shadow:0 10px 23px rgba(16,38,61,.08)}} .pp-welcome-mini-cards strong{{display:block;margin:7px 0 4px;color:#10263D;font-size:12px}} .pp-welcome-mini-cards span{{color:#718091;font-size:9px}}
      .pp-welcome-pillars{{max-width:1480px;margin:0 auto;display:grid;grid-template-columns:repeat(3,1fr);gap:12px;border-top:1px solid rgba(16,38,61,.11);padding-top:20px}} .pp-welcome-pillars article{{display:flex;gap:15px;padding:15px 16px;border-radius:14px;transition:background .15s ease,transform .15s ease}} .pp-welcome-pillars article:hover{{background:rgba(255,255,255,.55);transform:translateY(-2px)}} .pp-welcome-pillars article>span{{display:grid;place-items:center;flex:0 0 34px;width:34px;height:34px;border-radius:10px;background:#10263D;color:#fff;font-size:10px;font-weight:850}} .pp-welcome-pillars small{{display:block;color:#F05A28;font-size:9px;font-weight:880;letter-spacing:.16em}} .pp-welcome-pillars strong{{display:block;margin:5px 0;color:#10263D;font-size:13px}} .pp-welcome-pillars p{{margin:0;color:#6A7A89!important;font-size:10px!important;line-height:1.55!important}} .pp-welcome-footer{{max-width:1480px;margin:24px auto 0;display:flex;justify-content:space-between;border-top:1px solid rgba(16,38,61,.08);padding-top:15px;color:#82909D;font-size:9px;font-weight:800;letter-spacing:.15em}} .pp-welcome-footer p{{margin:0!important;color:#82909D!important;font-size:9px!important}}
      .pp-welcome-product-intro,.pp-welcome-features,.pp-welcome-loop,.pp-welcome-trust,.pp-welcome-roadmap,.pp-welcome-closing{{max-width:1480px;margin-left:auto;margin-right:auto}}
      .pp-welcome-product-intro{{margin-top:112px;margin-bottom:34px}} .pp-product-kicker{{color:#53687B;font-size:9px;font-weight:900;letter-spacing:.18em}} .pp-product-intro-grid{{display:grid;grid-template-columns:1.06fr .94fr;gap:clamp(45px,8vw,130px);align-items:end;margin-top:17px}} .pp-product-intro-grid h2,.pp-loop-heading h2,.pp-trust-copy h2,.pp-welcome-roadmap h2,.pp-welcome-closing h2{{margin:0!important;color:#10263D!important;font-size:clamp(34px,4vw,61px)!important;line-height:1.03!important;letter-spacing:-.052em!important}} .pp-product-intro-grid h2 em{{color:#F05A28;font-style:normal}} .pp-product-intro-grid>div>p{{color:#5C7083!important;font-size:15px!important;line-height:1.7!important}} .pp-evidence-note{{display:flex;gap:11px;padding-top:13px;border-top:1px solid rgba(16,38,61,.12);font-size:11px!important;font-weight:650}} .pp-evidence-note i{{display:block;flex:0 0 8px;width:8px;height:8px;margin-top:5px;border-radius:50%;background:#3E8E72;box-shadow:0 0 0 5px rgba(62,142,114,.12)}}
      .pp-welcome-features{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-bottom:118px}} .pp-feature{{position:relative;min-height:290px;padding:27px 27px 25px;border:1px solid rgba(16,38,61,.10);border-radius:20px;overflow:hidden;background:rgba(255,255,255,.7);box-shadow:0 12px 35px rgba(16,38,61,.055);transition:transform .18s ease,box-shadow .18s ease}} .pp-feature:hover{{transform:translateY(-3px);box-shadow:0 18px 42px rgba(16,38,61,.09)}} .pp-feature-wide{{grid-column:span 2}} .pp-feature-number{{position:absolute;right:24px;top:22px;color:rgba(16,38,61,.23);font-size:10px;font-weight:900;letter-spacing:.13em}} .pp-feature>small{{color:#F05A28;font-size:9px;font-weight:900;letter-spacing:.17em}} .pp-feature h3{{max-width:740px;margin:35px 0 13px!important;color:#10263D!important;font-size:clamp(23px,2.4vw,37px)!important;line-height:1.08!important;letter-spacing:-.042em!important}} .pp-feature p{{max-width:780px;margin:0!important;color:#65788A!important;font-size:12px!important;line-height:1.68!important}}
      .pp-feature-dark{{min-height:330px;background:radial-gradient(circle at 86% 8%,rgba(240,90,40,.25),transparent 25%),#10263D;border-color:#10263D;box-shadow:0 20px 42px rgba(16,38,61,.16)}} .pp-feature-dark>small{{color:#F58A62}} .pp-feature-dark .pp-feature-number{{color:rgba(255,255,255,.26)}} .pp-feature-dark h3{{color:#fff!important}} .pp-feature-dark p{{color:#B9C6D0!important}} .pp-feature-tags{{position:absolute;left:27px;right:27px;bottom:25px;display:flex;flex-wrap:wrap;gap:7px}} .pp-feature-tags span{{padding:7px 9px;border:1px solid rgba(255,255,255,.16);border-radius:999px;color:#D7E0E7;font-size:8px;font-weight:800;letter-spacing:.07em;text-transform:uppercase}}
      .pp-feature-orange{{background:linear-gradient(145deg,#F26A3B,#F05A28);border-color:#F05A28;box-shadow:0 18px 38px rgba(240,90,40,.16)}} .pp-feature-orange>small,.pp-feature-orange h3,.pp-feature-orange p{{color:#fff!important}} .pp-feature-orange .pp-feature-number{{color:rgba(255,255,255,.48)}} .pp-condition-row,.pp-decision-row{{display:flex;flex-wrap:wrap;gap:7px;margin-top:24px}} .pp-condition-row span,.pp-decision-row span{{padding:7px 9px;border-radius:8px;background:#EEE8DE;color:#4E6477;font-size:8px;font-weight:880;letter-spacing:.12em}}
      .pp-feature-race{{background:linear-gradient(135deg,#FFF 0%,#F5F0E8 100%)}} .pp-race-track{{display:grid;grid-template-columns:repeat(3,1fr);align-items:center;margin:34px 7px 8px;height:3px;background:linear-gradient(90deg,#10263D,#3E8E72,#F05A28)}} .pp-race-track i{{display:block;width:15px;height:15px;border:4px solid #F8F5EF;border-radius:50%;background:#10263D;box-shadow:0 0 0 1px rgba(16,38,61,.18)}} .pp-race-track i:nth-child(2){{justify-self:center;background:#3E8E72}} .pp-race-track i:nth-child(3){{justify-self:end;background:#F05A28}} .pp-race-labels{{display:flex;justify-content:space-between;color:#718091;font-size:8px;font-weight:900;letter-spacing:.12em}} .pp-feature-green{{background:linear-gradient(145deg,#EAF4EF,#F8F5EF);border-top:3px solid #3E8E72}} .pp-feature-fuel{{min-height:315px;background:radial-gradient(circle at 90% 20%,rgba(62,142,114,.16),transparent 30%),linear-gradient(135deg,#FBF7EF,#EEF4EE)}} .pp-feature-fuel h3{{max-width:820px}} .pp-fuel-tags span{{border-color:rgba(62,142,114,.22);color:#39785F;background:rgba(255,255,255,.58)}}
      .pp-welcome-loop{{margin-bottom:116px}} .pp-loop-heading{{display:grid;grid-template-columns:1fr .58fr;gap:60px;align-items:end;margin:17px 0 28px}} .pp-loop-heading p{{margin:0!important;color:#65788A!important;font-size:13px!important;line-height:1.65!important}} .pp-loop-grid{{display:grid;grid-template-columns:repeat(5,1fr);overflow:hidden;border:1px solid rgba(16,38,61,.11);border-radius:20px;background:rgba(255,255,255,.56);box-shadow:0 14px 38px rgba(16,38,61,.055)}} .pp-loop-grid article{{position:relative;min-height:225px;padding:24px 19px}} .pp-loop-grid article+article{{border-left:1px solid rgba(16,38,61,.11)}} .pp-loop-grid article:not(:last-child):after{{content:"→";position:absolute;z-index:2;right:-12px;top:31px;display:grid;place-items:center;width:24px;height:24px;border:1px solid rgba(16,38,61,.12);border-radius:50%;background:#F5F1EA;color:#F05A28;font-size:13px;font-weight:900}} .pp-loop-grid b{{display:block;color:rgba(16,38,61,.23);font-size:10px;letter-spacing:.15em}} .pp-loop-grid small{{display:block;margin:30px 0 8px;color:#F05A28;font-size:8px;font-weight:900;letter-spacing:.16em}} .pp-loop-grid strong{{display:block;font-size:15px;line-height:1.3}} .pp-loop-grid p{{color:#687A8B!important;font-size:10px!important;line-height:1.55!important}}
      .pp-welcome-trust{{display:grid;grid-template-columns:1.05fr .95fr;gap:clamp(50px,9vw,140px);align-items:center;margin-bottom:116px;padding:55px clamp(30px,5vw,75px);border-radius:26px;background:#10263D;box-shadow:0 24px 54px rgba(16,38,61,.16)}} .pp-trust-copy .pp-product-kicker{{color:#F58A62}} .pp-trust-copy h2{{margin:17px 0!important;color:#fff!important;font-size:clamp(33px,3.8vw,56px)!important}} .pp-trust-copy>p{{color:#B9C6D0!important;font-size:13px!important;line-height:1.7!important}} .pp-trust-principles article{{display:flex;gap:16px;padding:18px 0;border-bottom:1px solid rgba(255,255,255,.12)}} .pp-trust-principles article:first-child{{border-top:1px solid rgba(255,255,255,.12)}} .pp-trust-principles article>span{{display:grid;place-items:center;flex:0 0 34px;width:34px;height:34px;border-radius:10px;background:rgba(240,90,40,.17);color:#F58A62;font-size:9px;font-weight:900}} .pp-trust-principles strong{{color:#fff;font-size:13px}} .pp-trust-principles p{{margin:4px 0 0!important;color:#9FB0BD!important;font-size:10px!important}}
      .pp-welcome-roadmap{{display:grid;grid-template-columns:.75fr 1.25fr;gap:clamp(45px,8vw,120px);align-items:start;margin-bottom:112px}} .pp-welcome-roadmap h2{{margin:17px 0!important;font-size:clamp(34px,3.5vw,53px)!important}} .pp-welcome-roadmap>div>p{{color:#65788A!important;font-size:12px!important;line-height:1.68!important}} .pp-roadmap-items{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}} .pp-roadmap-items article{{min-height:190px;padding:22px 18px;border:1px solid rgba(16,38,61,.10);border-radius:16px;background:rgba(255,255,255,.62)}} .pp-roadmap-items small{{color:#3E8E72;font-size:8px;font-weight:900;letter-spacing:.15em}} .pp-roadmap-items strong{{display:block;margin:34px 0 8px;font-size:14px;line-height:1.3}} .pp-roadmap-items p{{margin:0!important;color:#6C7D8C!important;font-size:10px!important;line-height:1.55!important}}
      .pp-welcome-closing{{display:grid;grid-template-columns:auto 1fr auto;gap:30px;align-items:center;padding:42px clamp(28px,4vw,58px);border-radius:24px;background:linear-gradient(115deg,#F05A28,#E94E1B);box-shadow:0 22px 48px rgba(240,90,40,.19)}} .pp-closing-mark{{display:grid;place-items:center;width:64px;height:64px;border:2px solid rgba(255,255,255,.72);border-radius:18px;color:#fff;font-size:23px;font-weight:950;letter-spacing:-.08em}} .pp-welcome-closing .pp-product-kicker{{color:rgba(255,255,255,.75)}} .pp-welcome-closing h2{{margin-top:9px!important;color:#fff!important;font-size:clamp(30px,3.5vw,50px)!important}} .pp-welcome-enter-light{{min-width:260px;background:#fff;color:#10263D!important;box-shadow:0 12px 28px rgba(129,44,17,.22)}} .pp-welcome-enter-light:hover{{background:#F8F5EF;color:#10263D!important}} .pp-welcome-enter-light b{{color:#fff}} .pp-welcome-closing+.pp-welcome-footer{{margin-top:28px}}
      @keyframes pp-route-flow{{to{{stroke-dashoffset:-120}}}} @media(prefers-reduced-motion:reduce){{.pp-route-line{{animation:none}}.pp-welcome-enter,.pp-welcome-pillars article{{transition:none}}}}
      @media(max-width:1050px){{.pp-welcome-hero{{grid-template-columns:1fr;margin-top:55px}}.pp-welcome-copy{{max-width:790px}}.pp-welcome-stage{{min-height:auto}}.pp-welcome-stage-top{{width:94%;margin:0 auto;grid-template-columns:minmax(450px,1fr) minmax(190px,.34fr)}}.pp-welcome-passport{{margin:0;width:100%}}.pp-welcome-mini-cards{{width:94%;margin:18px auto 0}}.pp-welcome-features{{grid-template-columns:repeat(2,1fr)}}.pp-feature-wide{{grid-column:span 2}}.pp-loop-grid{{grid-template-columns:repeat(2,1fr)}}.pp-loop-grid article+article{{border-left:0}}.pp-loop-grid article{{border-bottom:1px solid rgba(16,38,61,.11)}}.pp-loop-grid article:nth-child(even){{border-left:1px solid rgba(16,38,61,.11)}}.pp-loop-grid article:after{{display:none!important}}.pp-welcome-roadmap{{grid-template-columns:1fr}}}}
      @media(max-width:680px){{.pp-welcome-shell{{padding:18px 17px 24px}}.pp-welcome-preview{{display:none}}.pp-welcome-brand span{{font-size:8px}}.pp-welcome-hero{{margin-top:45px;gap:42px}}.pp-welcome-copy h1{{font-size:clamp(43px,14vw,64px)!important}}.pp-welcome-lead{{font-size:15px!important}}.pp-welcome-enter{{width:100%;min-width:0}}.pp-athlete-choices{{grid-template-columns:1fr}}.pp-welcome-passport{{padding:20px 18px;transform:none}}.pp-welcome-signal-grid{{grid-template-columns:1fr}}.pp-welcome-route{{width:100%;height:115px}}.pp-welcome-mini-cards,.pp-welcome-pillars,.pp-welcome-features,.pp-loop-grid,.pp-roadmap-items{{grid-template-columns:1fr}}.pp-welcome-mini-cards{{width:100%}}.pp-welcome-pillars article{{padding:12px 6px}}.pp-welcome-product-intro{{margin-top:76px}}.pp-product-intro-grid,.pp-loop-heading,.pp-welcome-trust,.pp-welcome-roadmap{{grid-template-columns:1fr;gap:24px}}.pp-feature-wide{{grid-column:span 1}}.pp-feature{{min-height:280px}}.pp-feature-dark,.pp-feature-fuel{{min-height:355px}}.pp-loop-grid article,.pp-loop-grid article:nth-child(even){{border-left:0}}.pp-welcome-trust{{padding:38px 24px}}.pp-welcome-closing{{grid-template-columns:1fr}}.pp-closing-mark{{display:none}}.pp-welcome-enter-light{{width:100%}}}}
      @media(max-width:680px){{.pp-welcome-stage{{min-height:auto}}.pp-welcome-stage-top{{width:100%;grid-template-columns:1fr}}.pp-welcome-runner-frame{{position:absolute;inset:0;min-height:0;border:0;background:transparent;box-shadow:none;pointer-events:none}}.pp-welcome-runner-frame:before{{display:none}}.pp-welcome-runner{{right:-160px;bottom:-92px;height:500px;opacity:.11;filter:saturate(.72) drop-shadow(0 20px 22px rgba(16,38,61,.15))}}.pp-welcome-passport{{position:relative;z-index:2;background:linear-gradient(145deg,rgba(255,255,255,.96),rgba(247,243,236,.92))}}}}
    </style>
    """


def show_welcome_page() -> None:
    st.html(build_welcome_page_html(get_athletes()))
