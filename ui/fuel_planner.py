"""Production Weekly Fuel Planner presentation."""

from __future__ import annotations

import datetime
import html

import streamlit as st

from core.fuel_planner import (
    BUDGET_STYLES,
    DEMANDS,
    DIETARY_STYLES,
    MEAL_SLOTS,
    RECIPE_BY_ID,
    MealSelection,
    NutritionProfile,
    build_shopping_list,
    default_nutrition_profile,
    format_quantity,
    load_household_week_selections,
    load_next_fuel_week,
    load_nutrition_profile,
    load_week_selections,
    meal_options,
    parse_terms,
    save_nutrition_profile,
    save_week_selections,
    shopping_list_csv,
)
from ui.athlete_selection import render_athlete_id_selector
from ui.athlete_selection import (
    SESSION_ID_KEY,
    SESSION_NAME_KEY,
    athlete_name,
    get_athletes,
)
from ui.nutrition_coach_navigation import (
    clear_nutrition_coach_params,
    read_nutrition_coach_request,
)


FUEL_PLANNER_CACHE_SCHEMA = 2


def _escape(value) -> str:
    return html.escape(str(value or ""))


def _friendly_date(value: str) -> str:
    try:
        return datetime.date.fromisoformat(value[:10]).strftime("%-d %b %Y")
    except (TypeError, ValueError):
        return str(value)


@st.cache_data(show_spinner=False, ttl=120)
def _cached_fuel_week(athlete_id: int, reference_date: datetime.date, schema: int):
    del schema
    return load_next_fuel_week(athlete_id, reference_date=reference_date)


def _apply_nutrition_coach_request() -> None:
    request = read_nutrition_coach_request(st.query_params)
    if request is None:
        return
    rows_by_id = {int(row[0]): row for row in get_athletes()}
    row = rows_by_id.get(request.athlete_id)
    if row is not None:
        st.session_state[SESSION_ID_KEY] = request.athlete_id
        st.session_state[SESSION_NAME_KEY] = athlete_name(row)
    clear_nutrition_coach_params(st.query_params)


def _key_fuel_day(week):
    if week is None or not week.days:
        return None
    priority = {
        "Long run / race": 3,
        "Quality": 2,
        "Easy": 1,
        "Rest / recovery": 0,
    }
    return max(
        enumerate(week.days),
        key=lambda item: (priority.get(item[1].demand, 0), -item[0]),
    )[1]


def build_nutrition_coach_hero_html(
    athlete_display_name: str,
    profile: NutritionProfile,
    week=None,
) -> str:
    first_name = (athlete_display_name or "Athlete").split()[0]
    key_day = _key_fuel_day(week)
    if key_day is None:
        headline = "Your food preferences are the coaching foundation."
        briefing = (
            "Save an active Training Block and Nutrition Coach will turn its "
            "real sessions into a practical meal plan and shopping list."
        )
        key_label = "Training week needed"
        key_detail = "No meal plan invented"
        week_label = "Waiting for an approved block"
    else:
        headline = "Fuel the work, without making food complicated."
        briefing = (
            f"The next key demand is {key_day.session_type.lower()} on "
            f"{key_day.day}. Meals can rotate around that session while "
            "remaining familiar, practical and preference-aware."
        )
        key_label = f"{key_day.day} · {key_day.demand}"
        key_detail = key_day.session_detail
        week_label = (
            f"{_friendly_date(week.start_date)}–"
            f"{_friendly_date(week.end_date)}"
        )
    exclusions = len(profile.allergies) + len(profile.dislikes)
    return f"""
    <main class="nc-hero">
      <section class="nc-briefing">
        <div class="nc-eyebrow"><span></span>Nutrition Coach · {_escape(first_name)}</div>
        <h1>{_escape(headline)}</h1>
        <p>{_escape(briefing)}</p>
        <div class="nc-key-session"><small>NEXT KEY FUEL DEMAND</small><strong>{_escape(key_label)}</strong><span>{_escape(key_detail)}</span></div>
      </section>
      <section class="nc-profile-card">
        <div class="nc-profile-top"><span>ATHLETE FOOD PROFILE</span><b>ACTIVE</b></div>
        <h2>{_escape(profile.dietary_style)}</h2>
        <p>{_escape(week_label)}</p>
        <div class="nc-profile-grid">
          <div><small>OPTIONS</small><strong>3 per meal</strong><span>1 recommendation + 2 alternatives</span></div>
          <div><small>COOKING</small><strong>≤ {profile.max_cook_minutes} min</strong><span>{'Leftovers welcomed' if profile.use_leftovers else 'Fresh meals preferred'}</span></div>
          <div><small>SHOPPING</small><strong>{profile.servings} serving{'s' if profile.servings != 1 else ''}</strong><span>{_escape(profile.budget_style)}</span></div>
          <div><small>FILTERS</small><strong>{exclusions}</strong><span>allergies and dislikes</span></div>
        </div>
      </section>
    </main>
    <style>
      .nc-hero{{--navy:#082943;--ink:#10263d;--green:#2f9a72;--orange:#f15a2a;display:grid;grid-template-columns:minmax(0,1.15fr) minmax(360px,.85fr);overflow:hidden;margin:12px 0 24px;border:1px solid #d9d3ca;border-radius:24px;background:#fff;box-shadow:0 18px 42px rgba(16,38,61,.10);font-family:"Avenir Next",Inter,system-ui,sans-serif}}
      .nc-briefing{{position:relative;padding:35px 38px;background:radial-gradient(circle at 90% 15%,rgba(47,154,114,.28),transparent 34%),linear-gradient(125deg,#082943,#0b3852);color:#fff}}
      .nc-eyebrow{{display:flex;align-items:center;gap:10px;color:#8de0bd;font-size:12px;font-weight:800;letter-spacing:.13em;text-transform:uppercase}} .nc-eyebrow span{{width:31px;height:3px;border-radius:2px;background:var(--orange)}}
      .nc-briefing h1{{max-width:720px;margin:22px 0 14px;color:#fff!important;font-size:clamp(31px,3vw,48px);line-height:1.02;letter-spacing:-.045em}} .nc-briefing>p{{max-width:720px;margin:0;color:#d8e5eb!important;font-size:16px;line-height:1.58}}
      .nc-key-session{{display:grid;gap:4px;margin-top:31px;padding-top:20px;border-top:1px solid rgba(255,255,255,.16)}} .nc-key-session small{{color:#8de0bd;font-size:11px;font-weight:800;letter-spacing:.11em}} .nc-key-session strong{{color:#fff;font-size:18px}} .nc-key-session span{{color:#b9cad4;font-size:13px}}
      .nc-profile-card{{padding:32px 34px;background:radial-gradient(circle at 100% 0,rgba(241,90,42,.10),transparent 32%),#fbf8f2}} .nc-profile-top{{display:flex;justify-content:space-between;color:#71818d;font-size:11px;font-weight:800;letter-spacing:.1em}} .nc-profile-top b{{padding:5px 8px;border-radius:999px;background:#e7f5ed;color:#27845f;font-size:9px}}
      .nc-profile-card h2{{margin:22px 0 4px;color:var(--ink)!important;font-size:33px;line-height:1}} .nc-profile-card>p{{margin:0;color:#72818c;font-size:13px}}
      .nc-profile-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:25px}} .nc-profile-grid div{{min-height:100px;padding:14px;border:1px solid #e5dfd6;border-radius:13px;background:rgba(255,255,255,.75)}} .nc-profile-grid small,.nc-profile-grid strong,.nc-profile-grid span{{display:block}} .nc-profile-grid small{{color:#83909a;font-size:10px;font-weight:800;letter-spacing:.09em}} .nc-profile-grid strong{{margin-top:8px;color:var(--ink);font-size:16px}} .nc-profile-grid span{{margin-top:4px;color:#73818c;font-size:11px;line-height:1.35}}
      @media(max-width:900px){{.nc-hero{{grid-template-columns:1fr}}}} @media(max-width:560px){{.nc-briefing,.nc-profile-card{{padding:26px 22px}}.nc-profile-grid{{grid-template-columns:1fr}}}}
    </style>
    """


def build_nutrition_week_strip_html(week) -> str:
    cards = "".join(
        f"""
        <article class="nc-week-day nc-demand-{_escape(day.demand.lower().replace(' / ', '-').replace(' ', '-'))}">
          <small>{_escape(day.day[:3].upper())}</small>
          <strong>{_escape(day.session_type)}</strong>
          <span>{_escape(day.demand)}</span>
        </article>
        """
        for day in week.days
    )
    return f"""
    <section class="nc-week">
      <div class="nc-section-head"><div><small>THE TRAINING–FOOD CONNECTION</small><h2>One week, seven different demands.</h2></div><span>Meals support the plan; they never rewrite it.</span></div>
      <div class="nc-week-grid">{cards}</div>
    </section>
    <style>
      .nc-week{{margin:0 0 25px;padding:25px;border:1px solid #ded8cf;border-radius:20px;background:#fff;box-shadow:0 10px 25px rgba(16,38,61,.055);font-family:"Avenir Next",Inter,system-ui,sans-serif}} .nc-section-head{{display:flex;align-items:flex-end;justify-content:space-between;gap:20px}} .nc-section-head small{{color:#2f9a72;font-size:11px;font-weight:850;letter-spacing:.12em}} .nc-section-head h2{{margin:7px 0 0;color:#10263d!important;font-size:27px;letter-spacing:-.035em}} .nc-section-head>span{{color:#71818d;font-size:12px}}
      .nc-week-grid{{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px;margin-top:20px}} .nc-week-day{{min-height:116px;padding:14px 12px;border:1px solid #e4ded5;border-radius:13px;background:#fbfaf7}} .nc-week-day small,.nc-week-day strong,.nc-week-day span{{display:block}} .nc-week-day small{{color:#81909a;font-size:10px;font-weight:850;letter-spacing:.1em}} .nc-week-day strong{{margin-top:15px;color:#10263d;font-size:14px;line-height:1.2}} .nc-week-day span{{margin-top:8px;color:#72818c;font-size:10px;line-height:1.3}} .nc-demand-quality,.nc-demand-long-run-race{{border-top:3px solid #f15a2a;background:#fff8f3}} .nc-demand-easy{{border-top:3px solid #2f9a72}}
      @media(max-width:1050px){{.nc-week-grid{{grid-template-columns:repeat(4,minmax(0,1fr))}}}} @media(max-width:620px){{.nc-section-head{{align-items:flex-start;flex-direction:column}}.nc-week-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
    </style>
    """


def build_fuel_week_overview_html(week, profile: NutritionProfile) -> str:
    counts = {demand: 0 for demand in DEMANDS}
    for day in week.days:
        counts[day.demand] += 1
    cards = "".join(
        f"<article><small>{_escape(demand.upper())}</small>"
        f"<strong>{count}</strong><p>day{'s' if count != 1 else ''}</p></article>"
        for demand, count in counts.items()
    )
    return f"""
    <section class="fp-overview">
      <div class="fp-overview-head">
        <div><small>NEXT TRAINING WEEK · WEEK {week.week_number}</small>
          <h2>{_escape(week.block_name)}</h2>
          <p>{_escape(_friendly_date(week.start_date))} → {_escape(_friendly_date(week.end_date))} · {_escape(week.phase)} · {_escape(week.emphasis)}</p>
        </div>
        <span>{_escape(profile.dietary_style.upper())} · {profile.servings} SERVING{'S' if profile.servings != 1 else ''}</span>
      </div>
      <div class="fp-demand-grid">{cards}</div>
      <div class="fp-lock">Meals respond to the approved training demand. They never change the Training Block.</div>
    </section>
    <style>
      .fp-overview{{container-type:inline-size;background:#fff;border:1px solid #DED8CE;border-top:4px solid #3E8E72;border-radius:17px;padding:24px;color:#10263D;font-family:Inter,system-ui,sans-serif;box-shadow:0 8px 22px rgba(16,38,61,.06)}}
      .fp-overview-head{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}} .fp-overview small{{font-size:12px;letter-spacing:.13em;font-weight:850;color:#718091}} .fp-overview h2{{font-size:27px;line-height:1.15;margin:7px 0}} .fp-overview-head p{{font-size:14px;line-height:1.55;color:#657687;margin:0}} .fp-overview-head>span{{background:#F7F3EC;border-radius:999px;padding:10px 13px;font-size:11px;font-weight:850;letter-spacing:.08em;white-space:nowrap}}
      .fp-demand-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:22px}} .fp-demand-grid article{{background:#F7F3EC;border:1px solid #E7E0D5;border-radius:13px;padding:15px}} .fp-demand-grid strong{{display:block;font-size:25px;margin-top:7px}} .fp-demand-grid p{{font-size:13px;color:#657687;margin:0}}
      .fp-lock{{margin-top:16px;padding-top:14px;border-top:1px solid #ECE7DE;font-size:13px;font-weight:700;color:#3E8E72}}
      @container (max-width:720px){{.fp-demand-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}.fp-overview-head{{flex-direction:column}}}} @container (max-width:420px){{.fp-overview{{padding:18px}}.fp-demand-grid{{grid-template-columns:1fr}}}}
    </style>
    """


def build_day_fuel_html(day) -> str:
    return f"""
    <section class="fp-day-intro">
      <div><small>{_escape(day.demand.upper())} FUEL</small><strong>{_escape(day.session_type)}</strong><p>{_escape(day.session_detail)}</p></div>
      <aside><b>DAY'S PURPOSE</b><p>{_escape(day.focus)}</p></aside>
      <div class="fp-guidance"><p><b>Before</b>{_escape(day.pre_training)}</p><p><b>During</b>{_escape(day.during_training)}</p><p><b>After</b>{_escape(day.recovery)}</p></div>
    </section>
    <style>
      .fp-day-intro{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);gap:12px;color:#10263D}} .fp-day-intro>div:first-child,.fp-day-intro aside{{background:#F7F3EC;border:1px solid #E7E0D5;border-radius:12px;padding:14px}} .fp-day-intro small,.fp-day-intro aside b{{display:block;font-size:11px;letter-spacing:.1em;font-weight:850;color:#718091}} .fp-day-intro strong{{display:block;font-size:18px;margin:5px 0}} .fp-day-intro p{{font-size:13px;line-height:1.5;margin:4px 0;color:#657687}} .fp-guidance{{grid-column:1/-1;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}} .fp-guidance p{{background:#fff;border-left:3px solid #3E8E72;padding:8px 11px}} .fp-guidance b{{display:block;color:#10263D;margin-bottom:3px}}
      @media(max-width:700px){{.fp-day-intro{{grid-template-columns:1fr}}.fp-guidance{{grid-column:1;grid-template-columns:1fr}}}}
    </style>
    """


def _plant_based_note(style: str) -> None:
    if style == "Vegan":
        st.info(
            "Vegan foundation: the recipes deliberately use pulses, tofu, "
            "fortified alternatives, nuts/seeds and vitamin-C-rich produce. "
            "Check reliable vitamin B12, vitamin D, iodine, calcium, iron and "
            "omega-3 sources; seek qualified advice before changing supplements."
        )
    elif style == "Vegetarian":
        st.info(
            "Vegetarian foundation: vary pulses, eggs/dairy where used, "
            "wholegrains, nuts, seeds and vegetables. Pair plant iron sources "
            "with vitamin-C-rich foods and keep calcium and vitamin B12 visible."
        )


def _profile_form(athlete_id: int, saved: NutritionProfile | None) -> None:
    profile = saved or default_nutrition_profile(athlete_id)
    with st.expander(
        "Nutrition profile",
        expanded=saved is None,
    ):
        st.caption(
            "These choices belong only to this athlete. Allergies are used to "
            "remove recipes, but labels and cross-contamination warnings must "
            "still be checked when buying food."
        )
        with st.form(f"fuel_profile_{athlete_id}"):
            first, second, third = st.columns(3)
            with first:
                dietary_style = st.selectbox(
                    "Dietary style",
                    DIETARY_STYLES,
                    index=DIETARY_STYLES.index(profile.dietary_style),
                )
                servings = st.number_input(
                    "Servings to shop for",
                    min_value=1,
                    max_value=12,
                    value=profile.servings,
                    step=1,
                )
            with second:
                cooking_options = (15, 30, 45, 60, 90)
                current_minutes = min(
                    cooking_options,
                    key=lambda value: abs(value - profile.max_cook_minutes),
                )
                max_cook = st.selectbox(
                    "Maximum cooking time",
                    cooking_options,
                    index=cooking_options.index(current_minutes),
                    format_func=lambda value: f"Up to {value} minutes",
                )
                budget = st.selectbox(
                    "Budget approach",
                    BUDGET_STYLES,
                    index=BUDGET_STYLES.index(profile.budget_style),
                )
            with third:
                use_leftovers = st.checkbox(
                    "Happy to batch cook / use leftovers",
                    value=profile.use_leftovers,
                )
                show_detail = st.checkbox(
                    "Show estimated calories and macros",
                    value=profile.show_nutrition_detail,
                )
            allergies = st.text_input(
                "Allergies or intolerances — separate with commas",
                value=", ".join(profile.allergies),
                placeholder="For example: milk, peanuts, gluten",
            )
            dislikes = st.text_input(
                "Foods to avoid — separate with commas",
                value=", ".join(profile.dislikes),
                placeholder="For example: mushrooms, tofu",
            )
            submitted = st.form_submit_button(
                "Save nutrition profile",
                type="primary",
                use_container_width=True,
            )
        if submitted:
            save_nutrition_profile(NutritionProfile(
                athlete_id=athlete_id,
                dietary_style=dietary_style,
                servings=int(servings),
                allergies=parse_terms(allergies),
                dislikes=parse_terms(dislikes),
                max_cook_minutes=int(max_cook),
                budget_style=budget,
                use_leftovers=use_leftovers,
                show_nutrition_detail=show_detail,
            ))
            st.cache_data.clear()
            st.success("Nutrition profile saved for this athlete.")
            st.rerun()


def build_recipe_choice_html(
    recipe,
    *,
    choice_label: str,
    show_detail: bool,
) -> str:
    tags = [recipe.dietary_style, f"{recipe.cook_minutes} min"]
    if recipe.cook_minutes <= 15:
        tags.append("Quick")
    if recipe.batch_friendly:
        tags.append("Batch-friendly")
    if recipe.carbohydrate_g >= 90:
        tags.append("Carbohydrate-supportive")
    if recipe.protein_g >= 35:
        tags.append("Higher protein")
    tag_markup = "".join(f"<span>{_escape(tag)}</span>" for tag in tags)
    nutrition = (
        f"<p class='nc-recipe-nutrition'>Approx. {recipe.energy_kcal} kcal · "
        f"{recipe.carbohydrate_g}g carbohydrate · {recipe.protein_g}g protein "
        "per serving.</p>"
        if show_detail else ""
    )
    allergen = (
        f"<small>Listed allergens: {_escape(', '.join(recipe.allergens))}</small>"
        if recipe.allergens else "<small>No listed catalogue allergens.</small>"
    )
    return f"""
    <article class="nc-recipe-card">
      <div class="nc-recipe-label">{_escape(choice_label)}</div>
      <h4>{_escape(recipe.name)}</h4>
      <p>{_escape(recipe.summary)}</p>
      {nutrition}
      <div class="nc-recipe-tags">{tag_markup}</div>
      {allergen}
    </article>
    <style>
      .nc-recipe-card{{margin:8px 0 17px;padding:16px 17px;border:1px solid #e2dcd3;border-left:4px solid #2f9a72;border-radius:13px;background:#fbfaf7;font-family:"Avenir Next",Inter,system-ui,sans-serif}} .nc-recipe-label{{color:#2f9a72;font-size:10px;font-weight:850;letter-spacing:.1em;text-transform:uppercase}} .nc-recipe-card h4{{margin:7px 0 5px;color:#10263d!important;font-size:17px}} .nc-recipe-card p{{margin:0;color:#647684;font-size:12px;line-height:1.45}} .nc-recipe-card .nc-recipe-nutrition{{margin-top:7px;color:#435d70}} .nc-recipe-tags{{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0 8px}} .nc-recipe-tags span{{padding:5px 8px;border-radius:999px;background:#eaf5ef;color:#34745d;font-size:9px;font-weight:750}} .nc-recipe-card>small{{color:#82909a;font-size:10px}}
    </style>
    """


def _meal_plan_form(week, profile: NutritionProfile, saved):
    selections = []
    incomplete = []
    with st.form(f"fuel_week_{week.athlete_id}_{week.start_date}"):
        st.markdown("### Choose the week’s meals")
        st.caption(
            "Every meal has one training-aware recommendation and two compatible "
            "alternatives. Choose what you will genuinely enjoy and eat."
        )
        if profile.dietary_style == "Omnivore":
            st.caption(
                "Omnivore balance: lunch and dinner lead with a rotating meat "
                "or fish choice and retain a plant-based alternative."
            )
        elif profile.dietary_style == "Pescatarian":
            st.caption(
                "Pescatarian balance: lunch and dinner lead with a rotating "
                "fish choice and retain a plant-based alternative."
            )
        for day in week.days:
            expanded = day.demand in {"Quality", "Long run / race"}
            label = (
                f"{day.day} · {_friendly_date(day.date)} — "
                f"{day.session_type}"
            )
            with st.expander(label, expanded=expanded):
                st.html(build_day_fuel_html(day))
                columns = st.columns(2)
                for index, slot in enumerate(MEAL_SLOTS):
                    with columns[index % 2]:
                        options = meal_options(profile, day, slot, count=3)
                        if not options:
                            incomplete.append((day.date, slot))
                            st.warning(
                                f"No safe {slot.lower()} remains after the "
                                "current diet, allergy, dislike and cooking filters."
                            )
                            continue
                        option_ids = [recipe.id for recipe in options]
                        existing = saved.get((day.date, slot))
                        selected_id = (
                            existing.recipe_id
                            if existing and existing.recipe_id in option_ids
                            else option_ids[0]
                        )
                        key = (
                            f"fuel_choice_{week.athlete_id}_{day.date}_"
                            f"{slot.replace(' ', '_')}"
                        )
                        if st.session_state.get(key) not in option_ids:
                            st.session_state[key] = selected_id
                        labels = {
                            recipe_id: (
                                f"Recommended · {RECIPE_BY_ID[recipe_id].name}"
                                if option_index == 0
                                else f"Alternative {option_index} · "
                                f"{RECIPE_BY_ID[recipe_id].name}"
                            )
                            for option_index, recipe_id in enumerate(option_ids)
                        }
                        chosen_id = st.radio(
                            slot,
                            option_ids,
                            key=key,
                            format_func=lambda recipe_id: labels[recipe_id],
                        )
                        recipe = RECIPE_BY_ID[chosen_id]
                        chosen_index = option_ids.index(chosen_id)
                        st.html(build_recipe_choice_html(
                            recipe,
                            choice_label=(
                                "Nutrition Coach recommendation"
                                if chosen_index == 0
                                else f"Selected alternative {chosen_index}"
                            ),
                            show_detail=profile.show_nutrition_detail,
                        ))
                        selections.append(MealSelection(
                            athlete_id=week.athlete_id,
                            training_block_id=week.training_block_id,
                            week_start=week.start_date,
                            meal_date=day.date,
                            meal_slot=slot,
                            recipe_id=chosen_id,
                            servings=profile.servings,
                        ))
        submitted = st.form_submit_button(
            "Save meal choices and update shopping list",
            type="primary",
            use_container_width=True,
            disabled=bool(incomplete),
        )
    if submitted:
        count = save_week_selections(selections)
        st.success(f"{count} meal choices saved. The shopping list is ready.")
        st.rerun()


def _shopping_list(week, profile: NutritionProfile, current_saved) -> None:
    expected = len(week.days) * len(MEAL_SLOTS)
    current = len(current_saved) == expected
    if current:
        for day in week.days:
            for slot in MEAL_SLOTS:
                choice = current_saved.get((day.date, slot))
                option_ids = {
                    recipe.id for recipe in meal_options(
                        profile, day, slot, count=3
                    )
                }
                if (
                    choice is None
                    or choice.recipe_id not in option_ids
                    or choice.servings != profile.servings
                ):
                    current = False
                    break
            if not current:
                break
    if not current:
        st.info(
            "Save all meal choices above to create the shopping list. "
            f"Currently saved and current: {len(current_saved)} of {expected}. "
            "If the profile changed, save the meal choices again."
        )
        return
    st.markdown("### Shopping list")
    controls = st.columns(2)
    with controls[0]:
        combine = st.checkbox(
            "Combine every athlete saved for this week",
            value=False,
            key=f"fuel_household_{week.start_date}",
        )
    with controls[1]:
        include_pantry = st.checkbox(
            "Include pantry staples",
            value=False,
            key=f"fuel_pantry_{week.athlete_id}_{week.start_date}",
        )
    if combine:
        named = load_household_week_selections(week.start_date)
        selections = [selection for _, selection in named]
        athlete_names = tuple(dict.fromkeys(name for name, _ in named))
        st.caption(
            "Combined saved choices for: "
            + (", ".join(athlete_names) if athlete_names else "this athlete")
            + "."
        )
    else:
        selections = list(current_saved.values())
        st.caption("Quantities reflect this athlete’s saved servings and meals.")
    items = build_shopping_list(
        selections,
        include_pantry=include_pantry,
    )
    categories = tuple(dict.fromkeys(item.category for item in items))
    category_columns = st.columns(2)
    counter = 0
    for category_index, category in enumerate(categories):
        with category_columns[category_index % 2]:
            st.markdown(f"**{category}**")
            for item in items:
                if item.category != category:
                    continue
                st.checkbox(
                    f"{item.name} — {format_quantity(item.amount, item.unit)}",
                    key=(
                        f"shop_{week.athlete_id}_{week.start_date}_"
                        f"{counter}_{int(combine)}_{int(include_pantry)}"
                    ),
                )
                counter += 1
    st.download_button(
        "Download shopping list (CSV)",
        data=shopping_list_csv(items),
        file_name=f"fuel-shopping-list-{week.start_date}.csv",
        mime="text/csv",
        use_container_width=True,
    )


def show_fuel_planner_page() -> None:
    st.markdown(
        """
        <style>
          [data-testid="stMainBlockContainer"] { max-width:1480px; padding-top:4rem; padding-bottom:3rem; }
          [data-testid="stSelectbox"] { max-width:430px; }
          [data-testid="stSelectbox"] > div > div { min-height:48px; border:1px solid #d9d3ca; border-radius:14px; background:#fff; box-shadow:0 8px 20px rgba(30,42,52,.055); }
          [data-testid="stExpander"] { border:1px solid #ded8cf; border-radius:15px; background:#fff; overflow:hidden; }
          [data-testid="stExpander"] summary { min-height:58px; font-weight:750; color:#10263d; }
          [data-testid="stTabs"] button { min-height:48px; font-size:14px; }
          [data-testid="stRadio"] label p { font-size:13px; color:#304b60; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _apply_nutrition_coach_request()
    athlete_id = render_athlete_id_selector(
        label="Athlete",
        label_visibility="collapsed",
    )
    if athlete_id is None:
        st.info("Add an athlete before asking the Nutrition Coach.")
        return
    saved_profile = load_nutrition_profile(athlete_id)
    profile = saved_profile or default_nutrition_profile(athlete_id)
    week = (
        _cached_fuel_week(
            athlete_id,
            datetime.date.today(),
            FUEL_PLANNER_CACHE_SCHEMA,
        )
        if saved_profile is not None else None
    )
    st.html(build_nutrition_coach_hero_html(
        st.session_state.get(SESSION_NAME_KEY, "Athlete"),
        profile,
        week,
    ))
    if saved_profile is None:
        st.info(
            "Set up this athlete’s food preferences first. Nutrition Coach will "
            "then filter every recommendation before it reaches the page."
        )
        _profile_form(athlete_id, None)
        return
    if week is None:
        st.warning(
            "No future week is available from an active, saved Training Block. "
            "Save or update the athlete’s Training Block first; Nutrition Coach "
            "will not invent sessions or meal demand."
        )
        _profile_form(athlete_id, saved_profile)
        return
    st.html(build_nutrition_week_strip_html(week))
    key_day = _key_fuel_day(week)
    if key_day is not None:
        st.markdown("### Next key-session fuelling")
        st.html(build_day_fuel_html(key_day))
    saved = load_week_selections(athlete_id, week.start_date)
    meal_tab, shopping_tab, preferences_tab = st.tabs(
        ("Meal choices", "Shopping list", "Food preferences")
    )
    with meal_tab:
        _meal_plan_form(week, saved_profile, saved)
    with shopping_tab:
        _shopping_list(week, saved_profile, saved)
    with preferences_tab:
        _plant_based_note(saved_profile.dietary_style)
        _profile_form(athlete_id, saved_profile)
    st.caption(
        "Food quantities and optional calories/macros are planning estimates, "
        "not diagnosis or treatment. Appetite, health needs and food labels "
        "take priority; use a registered sports dietitian for individual "
        "clinical or supplement advice."
    )
