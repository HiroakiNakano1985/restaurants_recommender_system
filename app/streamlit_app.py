"""Blueprint 2 §8: Streamlit demo UI.

A demo to actually run in the pitch. The key experience: toggle the same area between
"Google stars" and "Food Quality" and watch the ranking reshuffle.

Layout (§8):
  Sidebar : district / cuisine / sort-axis toggle [Google stars | Food Quality] / weight sliders
  Main    : scatter (star vs FQS, traps red) / store cards (explainability) / map (traps red, gems green)

State is held in Streamlit's session_state (widget keys). localStorage/sessionStorage is NOT used.
Data comes from app/data_loader.py (which only calls the existing pipeline). No logic is changed here.

Launch:  streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import os
import sys

# Because this is run as `streamlit run app/streamlit_app.py`, add the project root to the import path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from app.data_loader import build_dataset, classify
from rerank.personalize import personalize

st.set_page_config(page_title="BCN Food Quality vs Stars", layout="wide")

COLOR = {"trap": "#C44E52", "gem": "#55A868", "neutral": "#4C72B0"}
ARROW = {"trap": "🔻 tourist trap", "gem": "🔺 discovered gem", "neutral": "▪ no change"}
ALL = "(All)"          # sentinel for "no district/cuisine filter"
ANY = "(Any)"          # sentinel for "no max-price filter"
MODE_L1 = "Layer 1: browse all by FQS"
MODE_L2 = "Layer 2: recommend for me"
PRICE_OPTS = [ANY, "INEXPENSIVE", "MODERATE", "EXPENSIVE", "VERY_EXPENSIVE"]

# ----------------------------------------------------------------- sidebar
st.sidebar.header("⚙ Controls")

# Two-layer toggle (the point of this UI):
#   Layer 1 = de-biased FQS ranking, shared by all users.
#   Layer 2 = filter by the user's preferences, then order by FQS (rerank.personalize).
mode = st.sidebar.radio("Mode", [MODE_L1, MODE_L2], key="mode",
                        help="Layer 1: everyone sees the same FQS ranking. "
                             "Layer 2: your preferences select candidates, ordered by FQS.")

# Weights (live recompute: just calls the existing score_places/rerank)
st.sidebar.subheader("Weights (FQS recomputed live)")
half_life = st.sidebar.slider("time decay half-life (days)", 30, 1095, 365, step=15,
                              key="half_life",
                              help="Favor newer reviews. Smaller = more recency-weighted. Changing it moves ranks.")
norm_cuisine = st.sidebar.checkbox("cuisine normalization",
                                   value=True, key="norm_cuisine")

# Build the dataset (cached on the weights). `places` + `aspect_scores` feed Layer 2.
df_all, reviews_by_place, places, aspect_scores = build_dataset(
    half_life_days=half_life, normalize_by_cuisine=norm_cuisine)

# Preferences / filters (district & cuisine are shared by both modes)
is_l2 = (mode == MODE_L2)
st.sidebar.subheader("Your preferences" if is_l2 else "Browse")
districts = [ALL] + sorted(df_all["district"].dropna().unique().tolist())
cuisines = [ALL] + sorted(df_all["cuisine"].dropna().unique().tolist())
sel_district = st.sidebar.selectbox("District", districts, key="district")
sel_cuisine = st.sidebar.selectbox("Cuisine", cuisines, key="cuisine")

if is_l2:
    sel_price = st.sidebar.selectbox("Max price", PRICE_OPTS, key="price")
    sel_min_star = st.sidebar.select_slider("Min star", options=[0.0, 3.5, 4.0, 4.5],
                                            value=0.0, key="min_star")
    top_n = st.sidebar.slider("How many recommendations", 5, 30, 12, key="top_n")
    # Aspect weights — the heart of Layer 2: food-first vs ambiance-first give different recs.
    st.sidebar.markdown("**Aspect weights** (how much each matters to you)")
    w_food = st.sidebar.slider("food", 0.0, 1.0, 0.7, 0.05, key="w_food")
    w_service = st.sidebar.slider("service", 0.0, 1.0, 0.0, 0.05, key="w_service")
    w_ambiance = st.sidebar.slider("ambiance", 0.0, 1.0, 0.2, 0.05, key="w_ambiance")
    w_price = st.sidebar.slider("price", 0.0, 1.0, 0.1, 0.05, key="w_price")
    _wraw = {"food": w_food, "service": w_service, "ambiance": w_ambiance, "price": w_price}
    _wtot = sum(_wraw.values()) or 1.0
    st.sidebar.caption("normalized: " +
                       " · ".join(f"{a} {v / _wtot:.0%}" for a, v in _wraw.items()))
else:
    sort_axis = st.sidebar.radio("Sort by", ["Google stars", "Food Quality"],
                                 horizontal=True, key="sort_axis")

st.sidebar.caption("State is held in session_state (no localStorage). "
                   "Changing the weights recomputes FQS immediately.")

# ----------------------------------------------------------------- build the working set
rec_by_id = {}
if is_l2:
    # Layer 2: build prefs (incl. aspect weights), then personalize (filter -> weighted score -> top_n).
    prefs = {"weights": _wraw}
    if sel_district != ALL:
        prefs["districts"] = [sel_district]
    if sel_cuisine != ALL:
        prefs["cuisines"] = [sel_cuisine]
    if sel_price != ANY:
        prefs["max_price_level"] = sel_price
    if sel_min_star > 0:
        prefs["min_star"] = sel_min_star
    recs = personalize(places, prefs, aspect_scores=aspect_scores, top_n=top_n)
    rec_by_id = {r.place.place_id: r for r in recs}
    ordered_ids = [r.place.place_id for r in recs]
    if ordered_ids:
        df = df_all.set_index("place_id").loc[ordered_ids].reset_index()
    else:
        df = df_all.iloc[0:0].copy()
    df["kind"] = df["rank_delta"].apply(classify)
    df_sorted = df                       # already ordered by personalized score
    view_caption = (f"district=`{sel_district}` / cuisine=`{sel_cuisine}` / "
                    f"max price=`{sel_price}` / min star=`{sel_min_star}`")
else:
    # Layer 1: browse all, optionally filtered by district/cuisine, sorted by the toggle.
    df = df_all.copy()
    if sel_district != ALL:
        df = df[df["district"] == sel_district]
    if sel_cuisine != ALL:
        df = df[df["cuisine"] == sel_cuisine]
    df = df.copy()
    df["kind"] = df["rank_delta"].apply(classify)
    sort_col = "star_rating" if sort_axis == "Google stars" else "fqs"
    df_sorted = df.sort_values(sort_col, ascending=False)
    view_caption = (f"district=`{sel_district}` / cuisine=`{sel_cuisine}` / sort=`{sort_axis}`")

# ----------------------------------------------------------------- header
st.title("🍽 Barcelona — Google stars vs Food Quality")
st.info("⚠ This is a demo on **synthetic data**. Once real data (Google Places / "
        "Michelin/Repsol) is available, the same loader and same UI run the real thing.",
        icon="ℹ️")
st.markdown(f"**{'🎯 Layer 2 — recommended for you' if is_l2 else '🌐 Layer 1 — de-biased FQS ranking'}** · "
            f"{view_caption} · {len(df)} stores")

if df.empty:
    st.warning("No stores match. Loosen your preferences (price / min star / district / cuisine).")
    st.stop()

# ----------------------------------------------------------------- scatter
left, right = st.columns([1, 1])

with left:
    st.subheader("① Divergence scatter (star vs FQS)")
    sub = df.dropna(subset=["fqs"])
    fig, ax = plt.subplots(figsize=(6, 5))
    for kind in ("neutral", "gem", "trap"):
        s = sub[sub["kind"] == kind]
        if not s.empty:
            ax.scatter(s["star_rating"], s["fqs"], c=COLOR[kind], s=55, alpha=0.8,
                       edgecolors="white", linewidths=0.5,
                       label={"trap": "tourist trap (star-high / FQS-low)",
                              "gem": "discovered gem (star-low / FQS-high)",
                              "neutral": "other"}[kind])
    if len(sub) > 1:
        r = np.corrcoef(sub["star_rating"], sub["fqs"])[0, 1]
        ax.set_title(f"Pearson r = {r:.3f}  (lower = stronger divergence)", fontsize=10)
    ax.set_xlabel("Google star rating")
    ax.set_ylabel("Food Quality Score (FQS)")
    ax.grid(alpha=0.2)
    ax.legend(fontsize=7, loc="best")
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

# ----------------------------------------------------------------- map
with right:
    st.subheader("② Map (🔴 trap / 🟢 gem / 🔵 other)")
    try:
        import folium
        from streamlit_folium import st_folium

        center = [float(df["lat"].mean()), float(df["lng"].mean())]
        fmap = folium.Map(location=center, zoom_start=13, tiles="CartoDB positron")
        for _, row in df.iterrows():
            kind = row["kind"]
            popup = folium.Popup(
                f"<b>{row['name']}</b><br>⭐{row['star_rating']:.2f} / "
                f"🍽FQS {row['fqs']:.2f}<br>{ARROW[kind]} (Δ{row['rank_delta']})",
                max_width=240)
            folium.CircleMarker(
                location=[row["lat"], row["lng"]], radius=7,
                color=COLOR[kind], fill=True, fill_color=COLOR[kind],
                fill_opacity=0.85, popup=popup, tooltip=row["name"],
            ).add_to(fmap)
        st_folium(fmap, use_container_width=True, height=400, returned_objects=[])
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Failed to render the map (folium not installed?): {exc}")

# ----------------------------------------------------------------- store cards
if is_l2:
    st.subheader("③ Your recommendations (Layer 2: filtered, then ranked by your aspect weights)")
    st.caption("Move the **aspect weight** sliders (food / service / ambiance / price) and the "
               "ranking re-sorts: a food-first user and an ambiance-first user get different top "
               "picks. Each card shows the match-score breakdown.")
else:
    st.subheader(f"③ Store cards (sorted by {sort_axis}) — the toggle reshuffles the ranking")
    st.caption("Each card shows the star rank / FQS rank / their difference (Δ). "
               "Switching the sort axis changes the order, and Δ explains "
               "\"ranked #X by stars but #Y by FQS\".")

TOP_N = 12
shown = df_sorted.head(TOP_N)
if len(df_sorted) > TOP_N:
    st.caption(f"Showing the top {TOP_N} (of {len(df_sorted)} total).")

for _, row in shown.iterrows():
    kind = row["kind"]
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([3, 1, 1, 1.4])
        c1.markdown(f"**{row['name']}**  \n`{row['district']}` · `{row['cuisine']}`")
        c2.metric("⭐ Google", f"{row['star_rating']:.2f}", f"#{int(row['star_rank'])}")
        fqs_disp = "—" if row["fqs"] is None or np.isnan(row["fqs"]) else f"{row['fqs']:.2f}"
        c3.metric("🍽 FQS", fqs_disp, f"#{int(row['fqs_rank'])}")
        rec = rec_by_id.get(row["place_id"]) if is_l2 else None
        if rec is not None:
            c4.metric("🎯 Match", f"{rec.score:+.2f}")
        else:
            c4.markdown(f"<span style='color:{COLOR[kind]};font-weight:600'>{ARROW[kind]}</span><br>"
                        f"<small>rank Δ = star#{int(row['star_rank'])} − fqs#{int(row['fqs_rank'])} "
                        f"= **{int(row['rank_delta']):+d}**</small>", unsafe_allow_html=True)
        # Explainability
        fmr = row["food_mention_rate"]
        if rec is not None:
            # Layer 2: show how the match score breaks down across the weighted aspects.
            br = " · ".join(f"{a} {v:+.2f}" for a, v in rec.contributions.items()) or "(no weighted aspect present)"
            expl = (f"🎯 **Match breakdown**: {br}  →  **{rec.score:+.2f}**  ·  "
                    f"🔎 food mentioned in **{fmr:.0%}** of reviews")
            if row["rep_review"]:
                expl += f"  ·  \"{row['rep_review']}\""
        else:
            expl = (f"🔎 **Why this FQS**: **{fmr:.0%}** of this area's reviews mention food "
                    f"(of {row['n_reviews']}).")
            if row["rep_review"]:
                expl += f" Representative review: \"{row['rep_review']}\" (⭐{int(row['rep_rating'])})"
        st.caption(expl)

with st.expander("How to read this demo / data caveats"):
    st.markdown(
        "- **The toggle is the point**: viewing the same store set by Google stars vs Food "
        "Quality reshuffles the ranking.\n"
        "- 🔻**tourist trap** = high stars but low food score / 🔺**discovered gem** = low stars "
        "but real food.\n"
        "- FQS extracts each review's *food* aspect sentiment via ABSA and takes a weighted mean "
        "(with time decay etc.).\n"
        "- **Note this is synthetic data**. The divergence here is built into the generative "
        "design; the method is validated separately with real labels (Michelin/Repsol) "
        "(eval/run_eval.py).")
