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


FUEL_PLANNER_CACHE_SCHEMA = 1


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


def _recipe_label(recipe) -> str:
    extras = [f"{recipe.cook_minutes} min", recipe.dietary_style]
    if recipe.batch_friendly:
        extras.append("batch-friendly")
    return f"{recipe.name} · {' · '.join(extras)}"


def _recipe_caption(recipe, *, show_detail: bool) -> str:
    detail = recipe.summary
    if show_detail:
        detail += (
            f" Approx. {recipe.energy_kcal} kcal · "
            f"{recipe.carbohydrate_g}g carbohydrate · "
            f"{recipe.protein_g}g protein per serving."
        )
    if recipe.allergens:
        detail += " Listed allergens: " + ", ".join(recipe.allergens) + "."
    return detail


def _meal_plan_form(week, profile: NutritionProfile, saved):
    selections = []
    incomplete = []
    with st.form(f"fuel_week_{week.athlete_id}_{week.start_date}"):
        st.markdown("### Choose the week’s meals")
        st.caption(
            "Choose one option for every meal. Recommendations rotate through "
            "the week and prioritise the day’s training demand."
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
                        options = meal_options(profile, day, slot)
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
                        chosen_id = st.selectbox(
                            slot,
                            option_ids,
                            key=key,
                            format_func=lambda recipe_id: _recipe_label(
                                RECIPE_BY_ID[recipe_id]
                            ),
                        )
                        recipe = RECIPE_BY_ID[chosen_id]
                        st.caption(_recipe_caption(
                            recipe,
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
            "Save choices and build shopping list",
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
                    recipe.id for recipe in meal_options(profile, day, slot)
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
    selector, heading = st.columns([1, 2.7])
    with selector:
        athlete_id = render_athlete_id_selector(label_visibility="collapsed")
    with heading:
        st.markdown("## Weekly Fuel Planner")
        st.caption(
            "What should this athlete eat around next week’s approved training?"
        )
    if athlete_id is None:
        st.info("Add an athlete before planning meals.")
        return
    saved_profile = load_nutrition_profile(athlete_id)
    _profile_form(athlete_id, saved_profile)
    if saved_profile is None:
        st.info(
            "Save the athlete’s nutrition profile first. The planner will then "
            "filter every meal before making recommendations."
        )
        return
    _plant_based_note(saved_profile.dietary_style)
    week = _cached_fuel_week(
        athlete_id,
        datetime.date.today(),
        FUEL_PLANNER_CACHE_SCHEMA,
    )
    if week is None:
        st.warning(
            "No future week is available from an active, saved Training Block. "
            "Save or update the athlete’s Training Block first; Fuel Planner "
            "will not invent a training week."
        )
        return
    st.html(build_fuel_week_overview_html(week, saved_profile))
    saved = load_week_selections(athlete_id, week.start_date)
    _meal_plan_form(week, saved_profile, saved)
    _shopping_list(week, saved_profile, saved)
    st.caption(
        "Food quantities and optional calories/macros are planning estimates, "
        "not diagnosis or treatment. Appetite, health needs and food labels "
        "take priority; use a registered sports dietitian for individual "
        "clinical or supplement advice."
    )
