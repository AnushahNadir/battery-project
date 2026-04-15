import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Battery AI Co-Scientist",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── paths ─────────────────────────────────────────────────────────────────────
BASE  = Path(".").resolve()
MDL   = BASE / "data/processed/modeling"
TM    = BASE / "trained_models"

@st.cache_data
def load_json(p):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

@st.cache_data
def load_csv(p):
    p = Path(p)
    return pd.read_csv(p) if p.exists() else pd.DataFrame()

# ── load all artifacts ────────────────────────────────────────────────────────
df          = load_csv(BASE / "data/processed/cycle_features_with_rul.csv")
uncertainty = load_json(MDL / "uncertainty_estimates.json") or []
anomalies   = load_json(MDL / "anomalies.json") or []
survival    = load_csv(MDL / "survival_risk_predictions.csv")
metrics     = load_json(TM  / "model_metrics.json") or {}
conformal   = load_json(MDL / "conformal_coverage_report.json") or {}
feat_imp    = load_json(MDL / "feature_importance.json") or []
drift       = load_json(MDL / "drift_report.json") or {}
hypotheses  = load_json(MDL / "degradation_hypotheses.json") or []
counterfact = load_json(MDL / "counterfactual_examples.json") or []
unc_metrics = load_json(MDL / "uncertainty_metrics.json") or {}
cv_report   = load_json(MDL / "groupkfold_cv_report.json") or {}
manifest    = load_json(MDL / "manifest.json") or {}
report_path = MDL / "final_system_report.md"

u_df = pd.DataFrame(uncertainty)
a_df = pd.DataFrame(anomalies)

RUL_COL = next(
    (c for c in ["rul_ensemble_mean","rul_median","rul_ensemble","rul_ml","rul_pred"]
     if not u_df.empty and c in u_df.columns), None
)
has_bands = RUL_COL is not None and {"rul_lower_5","rul_upper_95"}.issubset(u_df.columns)

# ── temperature group helper ──────────────────────────────────────────────────
def temp_group(bid):
    n = int("".join(filter(str.isdigit, str(bid))) or 0)
    if 41 <= n <= 56: return "cold"
    if (29 <= n <= 32) or (38 <= n <= 40): return "hot"
    return "room"

GROUP_COLOR = {"room": "#2E8648", "hot": "#C0392B", "cold": "#007A8A"}
GROUP_LABEL = {"room": "Room (~24°C)", "hot": "Hot (43°C)", "cold": "Cold (<10°C)"}

battery_ids = sorted(df["battery_id"].dropna().astype(str).unique()) if not df.empty else []

# ── sidebar navigation ────────────────────────────────────────────────────────
st.sidebar.title("🔋 Battery AI Co-Scientist")
st.sidebar.caption(f"Pipeline run: {manifest.get('completed_at','—')[:19] if manifest else '—'}")
st.sidebar.markdown("---")

SECTIONS = [
    "📊  Executive Summary",
    "🤖  Model Performance",
    "📐  Conformal Coverage",
    "🔍  Battery Deep Dive",
    "⚠️  Risk Distribution",
    "📡  Drift Monitoring",
    "💡  Reasoning & Hypotheses",
    "📋  Final Report",
]
section = st.sidebar.radio("Go to", SECTIONS, label_visibility="collapsed")

st.sidebar.markdown("---")
st.sidebar.markdown("**Key Numbers**")
st.sidebar.metric("XGBoost RMSE", f"{metrics.get('rmse', 0):.2f} cycles")
st.sidebar.metric("Conformal Coverage", f"{unc_metrics.get('coverage_90_percent', 0):.1f}%", delta="target 90%")
st.sidebar.metric("Anomalies", len(anomalies))
st.sidebar.markdown("---")
st.sidebar.caption("Read-only decision-support tool. Not for safety-critical use.")


# ══════════════════════════════════════════════════════════════════════════════
# 1 · EXECUTIVE SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
if section == SECTIONS[0]:
    st.title("📊 Executive Summary")
    st.caption("The most important numbers from the full pipeline run — at a glance.")

    # Verdict banner
    verdict_line = ""
    if report_path.exists():
        for line in report_path.read_text(encoding="utf-8").splitlines():
            if "Overall Verdict" in line:
                verdict_line = line.replace("**", "").replace("Overall Verdict:", "").strip()
                break
    verdict_color = "#2E8648" if "PASS" in verdict_line and "CONDITIONAL" not in verdict_line else \
                    "#E68A00" if "CONDITIONAL" in verdict_line else "#C0392B"
    st.markdown(
        f"""<div style='background:{verdict_color}22;border-left:6px solid {verdict_color};
        padding:14px 20px;border-radius:6px;margin-bottom:20px'>
        <span style='font-size:1.3em;font-weight:700;color:{verdict_color}'>
        Overall Verdict: {verdict_line or "—"}</span></div>""",
        unsafe_allow_html=True,
    )

    # Top metrics row
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("XGBoost RMSE",   f"{metrics.get('rmse',0):.2f}",        "cycles  (target <100)")
    c2.metric("TCN RMSE",       f"{metrics.get('dl_sequence',{}).get('rmse',0):.2f}", "cycles")
    c3.metric("Stat. Baseline", f"{metrics.get('baseline_rmse',0):.1f}","cycles (excluded)")
    c4.metric("Coverage",       f"{unc_metrics.get('coverage_90_percent',0):.1f}%",   "target 90%")
    c5.metric("Anomalies",      str(len(anomalies)),                    "test cycles flagged")
    c6.metric("Test batteries", str(len(metrics.get("split_metadata",{}).get("test_batteries",[]))), "never seen in training")

    st.markdown("---")

    # Stage-by-stage verdict table
    st.subheader("Stage-by-Stage Results")
    stage_rows = []
    if report_path.exists():
        lines = report_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            for kw in ["Stage 3","Stage 4:","Stage 4.2","Stage 4.5","Stage 5","Stage 6"]:
                if line.startswith(f"### {kw}"):
                    label = line.replace("###","").strip()
                    verdict = "PASS" if "PASS" in label and "CONDITIONAL" not in label else \
                              "CONDITIONAL PASS" if "CONDITIONAL" in label else \
                              "FAIL" if "FAIL" in label else "—"
                    stage_rows.append({"Stage": label.split(" - ")[0].strip(),
                                       "Verdict": verdict})
    if stage_rows:
        sdf = pd.DataFrame(stage_rows)
        def color_verdict(val):
            c = "#d4edda" if val=="PASS" else "#fff3cd" if "CONDITIONAL" in val else "#f8d7da"
            return f"background-color:{c}"
        st.dataframe(sdf.style.applymap(color_verdict, subset=["Verdict"]),
                     use_container_width=True, hide_index=True)

    st.markdown("---")
    # Risk distribution summary
    st.subheader("Risk Category Distribution (all 2,790 observations)")
    risk_dist = unc_metrics.get("risk_distribution", {})
    if risk_dist:
        col1, col2 = st.columns([1, 2])
        with col1:
            total = sum(risk_dist.values())
            for cat, color in [("HIGH","#C0392B"),("MEDIUM","#E68A00"),("LOW","#2E8648")]:
                n = risk_dist.get(cat, 0)
                pct = 100 * n / total if total else 0
                st.markdown(
                    f"<div style='background:{color}22;border-left:5px solid {color};"
                    f"padding:10px 14px;border-radius:4px;margin-bottom:8px'>"
                    f"<b style='color:{color}'>{cat}</b>  "
                    f"<span style='font-size:1.4em;font-weight:700'>{n}</span>"
                    f"<span style='color:#888'> rows ({pct:.1f}%)</span></div>",
                    unsafe_allow_html=True,
                )
        with col2:
            fig, ax = plt.subplots(figsize=(5, 3.5))
            cats   = ["LOW", "MEDIUM", "HIGH"]
            vals   = [risk_dist.get(c,0) for c in cats]
            colors = ["#2E8648","#E68A00","#C0392B"]
            bars = ax.bar(cats, vals, color=colors, edgecolor="white", width=0.5)
            for b, v in zip(bars, vals):
                ax.text(b.get_x()+b.get_width()/2, b.get_height()+10,
                        str(v), ha="center", fontsize=10, fontweight="bold")
            ax.set_ylabel("Observations"); ax.set_title("Risk Category Counts")
            ax.grid(axis="y", alpha=0.3); ax.spines[["top","right"]].set_visible(False)
            st.pyplot(fig); plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# 2 · MODEL PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════
elif section == SECTIONS[1]:
    st.title("🤖 Model Performance")

    # RMSE comparison
    st.subheader("RMSE Comparison — All Three Models")
    col1, col2 = st.columns([3, 2])
    with col1:
        ml_rmse   = metrics.get("rmse", 0)
        dl_rmse   = metrics.get("dl_sequence", {}).get("rmse", 0)
        stat_rmse = metrics.get("baseline_rmse", 0)
        fig, ax = plt.subplots(figsize=(7, 3.8))
        models = ["Statistical\nBaseline\n(Exponential)", "TCN\n(Deep Learning)", "XGBoost\n(ML) ✓"]
        vals   = [stat_rmse, dl_rmse, ml_rmse]
        colors = ["#C0392B", "#007A8A", "#2E8648"]
        bars = ax.bar(models, vals, color=colors, edgecolor="white", width=0.5)
        ax.axhline(100, color="#1F3A5F", lw=2, ls="--", label="Pass threshold (100 cycles)")
        for b, v in zip(bars, vals):
            ax.text(b.get_x()+b.get_width()/2, b.get_height()+4,
                    f"{v:.1f}", ha="center", fontsize=11, fontweight="bold")
        ax.set_ylabel("RMSE (cycles)"); ax.set_title("Lower = better")
        ax.legend(); ax.grid(axis="y", alpha=0.3)
        ax.spines[["top","right"]].set_visible(False)
        st.pyplot(fig); plt.close(fig)
    with col2:
        st.markdown("#### What these numbers mean")
        st.markdown(
            "**RMSE** = how many cycles off the model is on average.\n\n"
            f"- **XGBoost: {ml_rmse:.2f} cycles** — best model, well below the 100-cycle pass threshold\n"
            f"- **TCN: {dl_rmse:.2f} cycles** — deep learning sequence model, close second\n"
            f"- **Statistical: {stat_rmse:.0f} cycles** — physics model, too inaccurate to use for predictions. "
            f"Excluded from the ensemble.\n\n"
            "The ensemble combines XGBoost (53.7%) + TCN (46.3%) using inverse-RMSE weighting."
        )

    st.markdown("---")

    # Feature importance
    st.subheader("What Does the Model Rely On? — Feature Importance")
    if feat_imp:
        fi_df = pd.DataFrame(feat_imp).sort_values("importance", ascending=True)
        fig, ax = plt.subplots(figsize=(8, 4.5))
        colors_fi = ["#1F3A5F" if v > 0.10 else "#007A8A" if v > 0.07 else "#AAAAAA"
                     for v in fi_df["importance"]]
        bars = ax.barh(fi_df["feature"], fi_df["importance"], color=colors_fi, edgecolor="white")
        for b, v in zip(bars, fi_df["importance"]):
            ax.text(v+0.002, b.get_y()+b.get_height()/2, f"{v:.3f}", va="center", fontsize=9)
        ax.set_xlabel("Feature Importance (XGBoost gain)")
        ax.set_title("Higher = model relies on this feature more")
        ax.spines[["top","right"]].set_visible(False)
        st.pyplot(fig); plt.close(fig)
        st.caption(
            "Top features: **energy_j** (total energy per cycle), **i_min** (minimum current), "
            "**v_mean** (mean voltage). These capture both how hard the battery is working "
            "and how degraded it already is."
        )

    st.markdown("---")

    # Cross-validation
    st.subheader("Cross-Validation — Honest Accuracy Estimate")
    st.markdown(
        "A single train/test split can be lucky. GroupKFold CV splits all 22 training batteries "
        "into 5 groups and tests each group in turn. The CV RMSE is a more conservative, "
        "more realistic accuracy estimate."
    )
    if cv_report and "folds" in cv_report:
        folds_df = pd.DataFrame(cv_report["folds"])[
            ["fold_index","n_train_batteries","n_val_batteries","rmse","mae"]
        ].rename(columns={"fold_index":"Fold","n_train_batteries":"Train batteries",
                          "n_val_batteries":"Val batteries","rmse":"RMSE","mae":"MAE"})
        folds_df["RMSE"] = folds_df["RMSE"].round(2)
        folds_df["MAE"]  = folds_df["MAE"].round(2)

        col1, col2 = st.columns([2, 1])
        with col1:
            st.dataframe(folds_df, use_container_width=True, hide_index=True)
        with col2:
            mean_cv = cv_report.get("mean_rmse", 0)
            std_cv  = cv_report.get("std_rmse", 0)
            st.metric("CV Mean RMSE", f"{mean_cv:.2f} ± {std_cv:.2f}")
            st.metric("Holdout test RMSE", f"{ml_rmse:.2f}")
            ratio = mean_cv / ml_rmse if ml_rmse else 0
            st.metric("CV / Test ratio", f"{ratio:.1f}×",
                      delta="warning: test set easier than average" if ratio > 1.5 else "OK",
                      delta_color="inverse" if ratio > 1.5 else "normal")

    # Per-battery RMSE
    st.markdown("---")
    st.subheader("Per-Battery RMSE — Test Set")
    pb = metrics.get("per_battery_rmse", {})
    if pb:
        pb_df = pd.DataFrame([{"Battery": k, "RMSE": round(v,2),
                                "Temp Group": temp_group(k)} for k,v in pb.items()])
        pb_df = pb_df.sort_values("RMSE")
        fig, ax = plt.subplots(figsize=(7, 3.5))
        bar_colors = [GROUP_COLOR[temp_group(b)] for b in pb_df["Battery"]]
        bars = ax.bar(pb_df["Battery"], pb_df["RMSE"], color=bar_colors, edgecolor="white", width=0.5)
        for b, v in zip(bars, pb_df["RMSE"]):
            ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.3,
                    f"{v:.1f}", ha="center", fontsize=9, fontweight="bold")
        patches = [mpatches.Patch(color=c, label=f"{g} — {GROUP_LABEL[g]}")
                   for g, c in GROUP_COLOR.items()]
        ax.legend(handles=patches, fontsize=8)
        ax.set_ylabel("RMSE (cycles)"); ax.set_title("Per-battery prediction error on test set")
        ax.grid(axis="y", alpha=0.3); ax.spines[["top","right"]].set_visible(False)
        st.pyplot(fig); plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# 3 · CONFORMAL COVERAGE
# ══════════════════════════════════════════════════════════════════════════════
elif section == SECTIONS[2]:
    st.title("📐 Conformal Coverage")
    st.markdown(
        "Conformal prediction wraps the XGBoost model and guarantees that the true RUL "
        "falls inside the predicted interval at least **90% of the time**. "
        "A separate calibration margin (q_hat) is fitted per temperature group."
    )

    overall = conformal.get("overall_empirical_coverage", 0)
    target  = conformal.get("target_coverage", 0.9)
    per_grp = conformal.get("per_group", {})

    # Overall banner
    color = "#2E8648" if overall >= target else "#C0392B"
    st.markdown(
        f"<div style='background:{color}22;border-left:6px solid {color};"
        f"padding:14px 20px;border-radius:6px;margin-bottom:20px'>"
        f"<span style='font-size:1.3em;font-weight:700;color:{color}'>"
        f"Overall empirical coverage: {overall*100:.1f}%</span>"
        f"<span style='color:#555'>  (target: {target*100:.0f}%)</span></div>",
        unsafe_allow_html=True,
    )

    # Per-group cards
    cols = st.columns(3)
    for i, grp in enumerate(["room","hot","cold"]):
        g = per_grp.get(grp, {})
        emp     = g.get("empirical_coverage", 0)
        q_hat   = g.get("q_hat", 0)
        strat   = g.get("strategy", "—")
        gap     = g.get("gap_vs_target", 0)
        ok      = emp >= target
        c       = GROUP_COLOR[grp]
        badge   = "✓ Above target" if ok else "✗ Below target"
        b_color = "#2E8648" if ok else "#C0392B"
        with cols[i]:
            st.markdown(
                f"<div style='border:2px solid {c};border-radius:10px;padding:16px;'>"
                f"<div style='color:{c};font-weight:700;font-size:1.1em'>{grp.upper()} — {GROUP_LABEL[grp]}</div>"
                f"<div style='font-size:2.5em;font-weight:700;margin:8px 0'>{emp*100:.1f}%</div>"
                f"<div style='color:#555;font-size:0.9em'>q_hat = {q_hat:.2f} cycles</div>"
                f"<div style='color:#555;font-size:0.9em'>Strategy: <b>{strat.upper()}</b></div>"
                f"<div style='color:#555;font-size:0.9em'>Gap vs target: {gap*100:+.1f}%</div>"
                f"<div style='color:{b_color};font-weight:700;margin-top:8px'>{badge}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # LOBO explanation
    st.subheader("Why LOBO for Cold Batteries?")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            "Cold batteries behave differently and there are only **3 cold calibration batteries**. "
            "With so few examples, standard split conformal under-covers cold batteries.\n\n"
            "**LOBO (Leave-One-Battery-Out)** fixes this by:\n"
            "1. For each cold battery, temporarily remove it\n"
            "2. Refit the model without it\n"
            "3. Score the error on the removed battery\n"
            "4. This gives errors representative of a truly unseen cold battery\n\n"
            "Result: cold coverage improved from **87.3% → 91.2%** ✓"
        )
    with col2:
        # Ablation comparison chart
        ablation = load_json(TM / "conformal_ablation.json")
        if ablation:
            methods = ablation.get("methods", {})
            groups  = ["room","hot","cold"]
            x       = np.arange(len(groups))
            w       = 0.25
            fig, ax = plt.subplots(figsize=(6, 4))
            for j, (mname, mcolor) in enumerate([
                ("Global split","#888888"),
                ("Stratified split","#007A8A"),
                ("Stratified LOBO","#2E8648"),
            ]):
                m = methods.get(mname, {})
                vals = [m.get("per_group",{}).get(g,{}).get("empirical_coverage",0)*100
                        for g in groups]
                ax.bar(x + j*w - w, vals, w, label=mname, color=mcolor, edgecolor="white")
            ax.axhline(90, color="#C0392B", lw=2, ls="--", label="Target 90%")
            ax.set_xticks(x); ax.set_xticklabels([g.capitalize() for g in groups])
            ax.set_ylabel("Empirical Coverage (%)"); ax.set_ylim(82, 105)
            ax.set_title("Ablation: Global vs Stratified vs LOBO")
            ax.legend(fontsize=8); ax.grid(axis="y", alpha=0.3)
            ax.spines[["top","right"]].set_visible(False)
            st.pyplot(fig); plt.close(fig)
        else:
            st.info("conformal_ablation.json not found in trained_models/.")

    st.markdown("---")
    st.subheader("What is q_hat?")
    st.markdown(
        "q_hat is the margin added/subtracted around each prediction to form the interval:\n\n"
        "**[ prediction − q_hat ,  prediction + q_hat ]**\n\n"
        f"- Room: q_hat = {per_grp.get('room',{}).get('q_hat',0):.1f} cycles\n"
        f"- Hot: q_hat = {per_grp.get('hot',{}).get('q_hat',0):.1f} cycles (inflated ×1.2 — only 1 hot cal battery)\n"
        f"- Cold: q_hat = {per_grp.get('cold',{}).get('q_hat',0):.1f} cycles (LOBO-calibrated)\n\n"
        "A larger q_hat means the model needs a wider margin to stay accurate for that group."
    )


# ══════════════════════════════════════════════════════════════════════════════
# 4 · BATTERY DEEP DIVE
# ══════════════════════════════════════════════════════════════════════════════
elif section == SECTIONS[3]:
    st.title("🔍 Battery Deep Dive")

    if df.empty:
        st.error("No cycle data found. Run preprocessing first."); st.stop()

    # ── battery selector ──────────────────────────────────────────────────────
    col_sel, col_info = st.columns([2, 3])
    with col_sel:
        selected = st.selectbox("Select a battery", battery_ids)
    grp = temp_group(selected)
    with col_info:
        st.markdown(
            f"<div style='background:{GROUP_COLOR[grp]}22;border-left:5px solid {GROUP_COLOR[grp]};"
            f"padding:10px 16px;border-radius:6px;margin-top:8px'>"
            f"<b style='color:{GROUP_COLOR[grp]}'>{selected}</b> — "
            f"{GROUP_LABEL[grp]}</div>",
            unsafe_allow_html=True,
        )

    df_b = df[df["battery_id"].astype(str)==selected].sort_values("cycle_index")

    # Quick stats
    eol_thr_val  = df_b["eol_capacity_threshold"].iloc[0] if "eol_capacity_threshold" in df_b.columns and len(df_b) else None
    eol_cyc_val  = int(df_b["eol_cycle"].iloc[0]) if "eol_cycle" in df_b.columns and len(df_b) else None
    n_anom       = len(a_df[a_df["battery_id"].astype(str)==selected]) if not a_df.empty else 0

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Total cycles recorded", len(df_b))
    c2.metric("Starting capacity",  f"{df_b['capacity'].iloc[0]:.3f} Ah" if len(df_b) else "—")
    c3.metric("Final capacity",     f"{df_b['capacity'].iloc[-1]:.3f} Ah" if len(df_b) else "—")
    c4.metric("EOL threshold",      f"{eol_thr_val:.3f} Ah" if eol_thr_val else "—",
              help="70% of starting capacity — when crossed the battery is worn out")
    c5.metric("EOL reached at cycle", str(eol_cyc_val) if eol_cyc_val else "—",
              help="First cycle where capacity dropped below the EOL threshold")
    c6.metric("Anomalies flagged",  n_anom)

    st.markdown("---")

    # ── chart 1: capacity degradation + anomalies ─────────────────────────────
    st.subheader("Chart 1 — Capacity Degradation + Anomaly Flags")
    st.markdown(
        "> **What to look for:** The line should slope downward over time as the battery wears out. "
        "When it crosses the red dashed line the battery has reached End-of-Life (EOL = 70% of starting capacity). "
        "Red dots are cycles where the battery behaved unexpectedly — large sudden drop or spike in the degradation trend."
    )
    fig, ax = plt.subplots(figsize=(10, 4))
    color = GROUP_COLOR[grp]
    ax.plot(df_b["cycle_index"], df_b["capacity"], color=color, lw=2, label="Capacity (Ah)")
    eol = df_b["eol_capacity_threshold"].iloc[0] if "eol_capacity_threshold" in df_b.columns else 1.6
    ax.axhline(eol, color="#C0392B", lw=1.5, ls="--", label=f"EOL threshold ({eol:.2f} Ah)")

    if not a_df.empty and "battery_id" in a_df.columns:
        an_b = a_df[a_df["battery_id"].astype(str)==selected].copy()
        if not an_b.empty:
            an_b["cycle_index"] = pd.to_numeric(an_b["cycle_index"], errors="coerce")
            merged = df_b.merge(an_b[["cycle_index"]].drop_duplicates(), on="cycle_index", how="inner")
            if not merged.empty:
                ax.scatter(merged["cycle_index"], merged["capacity"],
                           color="red", s=40, zorder=5, label=f"Anomaly ({len(merged)})")

    ax.set_xlabel("Cycle"); ax.set_ylabel("Capacity (Ah)")
    ax.set_title(f"Battery {selected} — Capacity Fade")
    ax.legend(); ax.grid(alpha=0.3); ax.spines[["top","right"]].set_visible(False)
    st.pyplot(fig); plt.close(fig)

    st.markdown("---")

    # ── chart 2: RUL prediction + conformal interval ──────────────────────────
    st.subheader("Chart 2 — RUL Prediction with 90% Conformal Interval")
    st.markdown(
        "> **What to look for:** Both lines should slope downward (fewer cycles remaining as time passes). "
        "The shaded band is the confidence interval — we are 90% sure the true RUL is somewhere inside it. "
        "A wide band means more uncertainty. The lines should be close together — large gaps mean the model struggled with this battery."
    )
    if RUL_COL and not u_df.empty and "battery_id" in u_df.columns:
        u_b = u_df[u_df["battery_id"].astype(str)==selected].sort_values("cycle_index")
        if not u_b.empty:
            show_bands = st.checkbox("Show uncertainty bands (5th–95th percentile)", value=True)
            fig, ax = plt.subplots(figsize=(10, 4))
            x   = pd.to_numeric(u_b["cycle_index"], errors="coerce")
            y   = pd.to_numeric(u_b[RUL_COL], errors="coerce")
            ax.plot(x, y, color=color, lw=2, label="Predicted RUL")
            if "RUL" in df_b.columns:
                ax.plot(df_b["cycle_index"], df_b["RUL"], color="#1F3A5F",
                        lw=1.5, ls="--", alpha=0.7, label="True RUL")
            if show_bands and has_bands:
                lo = pd.to_numeric(u_b["rul_lower_5"],  errors="coerce")
                hi = pd.to_numeric(u_b["rul_upper_95"], errors="coerce")
                ax.fill_between(x, lo, hi, alpha=0.2, color=color, label="90% conformal interval")
            ax.axhline(0, color="#C0392B", lw=1, ls=":", alpha=0.5)
            ax.set_xlabel("Cycle"); ax.set_ylabel("RUL (cycles)")
            ax.set_title(f"Battery {selected} — RUL Trajectory")
            ax.set_ylim(bottom=0); ax.legend(); ax.grid(alpha=0.3)
            ax.spines[["top","right"]].set_visible(False)
            st.pyplot(fig); plt.close(fig)
        else:
            st.info("No uncertainty data for this battery.")
    else:
        st.info("uncertainty_estimates.json not loaded.")

    st.markdown("---")

    # ── chart 3: survival / hazard risk ──────────────────────────────────────
    st.subheader("Survival Risk — Failure Probability")

    # plain english explainer always shown first
    st.markdown(
        "> **What is this chart?** For every cycle, we ask: "
        "*'if we are at this cycle right now, what is the chance this battery fails within the next 20 cycles?'* "
        "That probability drives the LOW / MEDIUM / HIGH risk label. "
        "The 20-cycle window is our **maintenance horizon** — if failure is likely within 20 cycles, act now."
    )

    if not survival.empty and "battery_id" in survival.columns:
        s_b = survival[survival["battery_id"].astype(str)==selected].sort_values("cycle_index")

        if not s_b.empty and {"hazard_prob","failure_prob_horizon"}.issubset(s_b.columns):

            # ── pull EOL info from feature data ──────────────────────────────
            eol_cycle = int(df_b["eol_cycle"].iloc[0]) if "eol_cycle" in df_b.columns else None
            eol_thr   = float(df_b["eol_capacity_threshold"].iloc[0]) if "eol_capacity_threshold" in df_b.columns else None
            horizon   = 20
            high_start = int(s_b[s_b["failure_prob_horizon"] >= 0.70]["cycle_index"].min()) \
                         if (s_b["failure_prob_horizon"] >= 0.70).any() else None

            # ── explain what is about to be shown for THIS battery ────────────
            rc = s_b["risk_category"].value_counts().to_dict() if "risk_category" in s_b.columns else {}

            if eol_cycle is not None:
                col_exp1, col_exp2 = st.columns(2)
                with col_exp1:
                    st.markdown(
                        f"**Battery {selected} — key facts:**\n\n"
                        f"- EOL threshold: **{eol_thr:.3f} Ah** (70% of starting capacity)\n"
                        f"- Capacity first crossed EOL at: **cycle {eol_cycle}**\n"
                        f"- Total recorded cycles: **{len(s_b)}**\n"
                        f"- Maintenance horizon used: **{horizon} cycles**"
                    )
                with col_exp2:
                    if high_start is not None:
                        cycles_before_high = high_start - 1
                        st.markdown(
                            f"**Why the graph looks the way it does:**\n\n"
                            f"- Cycles **1 – {cycles_before_high}**: EOL is more than {horizon} cycles away → failure prob = 0% → **LOW**\n"
                            f"- From cycle **{high_start}** onward: EOL is within {horizon} cycles → failure prob = 100% → **HIGH**\n\n"
                            f"The line jumps from 0 to 1 at cycle {high_start} because "
                            f"that is exactly when EOL enters the {horizon}-cycle window."
                        )
                    else:
                        st.markdown(
                            f"**Why the graph shows all zeros:**\n\n"
                            f"This battery's EOL (cycle {eol_cycle}) is always more than "
                            f"{horizon} cycles away from any recorded cycle, so the failure "
                            f"probability never rises above the thresholds."
                        )

            # ── risk category cards ───────────────────────────────────────────
            c1, c2, c3 = st.columns(3)
            for col_, cat, color_, meaning in [
                (c1, "LOW",    "#2E8648", f"EOL is more than {horizon} cycles away — no immediate concern"),
                (c2, "MEDIUM", "#E68A00", f"EOL is within {horizon}–{horizon*2} cycles — monitor closely"),
                (c3, "HIGH",   "#C0392B", f"EOL is within {horizon} cycles — act now"),
            ]:
                n = rc.get(cat, 0)
                col_.markdown(
                    f"<div style='background:{color_}22;border-left:5px solid {color_};"
                    f"padding:10px 14px;border-radius:5px;text-align:center'>"
                    f"<div style='color:{color_};font-weight:700;font-size:1em'>{cat}</div>"
                    f"<div style='font-size:2em;font-weight:700'>{n} cycles</div>"
                    f"<div style='color:#666;font-size:0.8em;margin-top:4px'>{meaning}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            st.markdown("")

            # ── the actual charts ─────────────────────────────────────────────
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)

            # top: hazard prob
            ax1.plot(s_b["cycle_index"], s_b["hazard_prob"], color="#E68A00", lw=2,
                     label="Hazard — P(fail at exactly this cycle)")
            if eol_cycle is not None and eol_cycle <= s_b["cycle_index"].max():
                ax1.axvline(eol_cycle, color="#C0392B", lw=2, ls="--", alpha=0.8,
                            label=f"EOL reached (cycle {eol_cycle})")
            ax1.set_ylabel("Hazard probability")
            ax1.set_title(
                f"Battery {selected} — Survival Risk\n"
                f"Top: per-cycle hazard   |   Bottom: probability of failing within next {horizon} cycles"
            )
            ax1.legend(fontsize=9); ax1.grid(alpha=0.3)
            ax1.spines[["top","right"]].set_visible(False)
            ax1.set_ylim(-0.05, 1.1)

            # bottom: horizon failure prob with coloured zones
            fp = s_b["failure_prob_horizon"]
            cyc = s_b["cycle_index"]
            ax2.fill_between(cyc, 0, fp,
                             where=fp < 0.30,
                             color="#2E8648", alpha=0.25, label="LOW zone (<30%)")
            ax2.fill_between(cyc, 0, fp,
                             where=(fp >= 0.30) & (fp < 0.70),
                             color="#E68A00", alpha=0.25, label="MEDIUM zone (30–70%)")
            ax2.fill_between(cyc, 0, fp,
                             where=fp >= 0.70,
                             color="#C0392B", alpha=0.25, label="HIGH zone (>70%)")
            ax2.plot(cyc, fp, color="#C0392B", lw=2)
            ax2.axhline(0.70, color="#C0392B", lw=1.2, ls="--", alpha=0.7)
            ax2.axhline(0.30, color="#E68A00", lw=1.2, ls="--", alpha=0.7)
            ax2.text(cyc.max()*0.98, 0.72, "HIGH threshold (70%)",
                     ha="right", fontsize=8, color="#C0392B")
            ax2.text(cyc.max()*0.98, 0.32, "MEDIUM threshold (30%)",
                     ha="right", fontsize=8, color="#E68A00")
            if eol_cycle is not None and eol_cycle <= cyc.max():
                ax2.axvline(eol_cycle, color="#C0392B", lw=2, ls="--", alpha=0.8)
                ax2.text(eol_cycle+1, 0.5, f"EOL\n(cycle {eol_cycle})",
                         fontsize=8, color="#C0392B", va="center")
            if high_start is not None:
                ax2.axvline(high_start, color="#888888", lw=1.2, ls=":", alpha=0.7)
                ax2.text(high_start+1, 0.1, f"HIGH risk\nstarts (cycle {high_start})",
                         fontsize=7.5, color="#888888", va="bottom")
            ax2.set_ylabel(f"P(fail within next {horizon} cycles)")
            ax2.set_xlabel("Cycle index")
            ax2.legend(fontsize=8, loc="center left")
            ax2.grid(alpha=0.3); ax2.spines[["top","right"]].set_visible(False)
            ax2.set_ylim(-0.05, 1.1)

            plt.tight_layout()
            st.pyplot(fig); plt.close(fig)

            # ── bottom plain-english summary ──────────────────────────────────
            st.markdown(
                f"**Reading this chart for battery {selected}:**\n\n"
                + (
                    f"The bottom chart is flat at **0%** for cycles 1–{high_start-1}, "
                    f"then jumps to **100%** from cycle {high_start} onward. "
                    f"This is because this battery reached EOL at cycle **{eol_cycle}** — "
                    f"a short life. From cycle {high_start}, EOL was always within {horizon} cycles, "
                    f"so failure probability is always 100%. The jump looks dramatic but is correct — "
                    f"it simply means 'we are now inside the danger window.'"
                    if high_start is not None and eol_cycle is not None
                    else
                    f"This battery's EOL was always outside the {horizon}-cycle horizon for all "
                    f"recorded cycles, so failure probability stays at 0% throughout."
                )
            )

        else:
            st.info("No survival data for this battery.")

    st.markdown("---")

    # ── multi-battery overlay ─────────────────────────────────────────────────
    st.subheader("Compare Multiple Batteries")
    compare = st.multiselect("Select batteries to overlay",
                             battery_ids, default=battery_ids[:6])
    mode = st.radio("Chart mode", ["Capacity Fade", "RUL Trajectory"], horizontal=True)

    if compare:
        fig, ax = plt.subplots(figsize=(11, 5))
        for bid in compare:
            c = GROUP_COLOR[temp_group(bid)]
            if mode == "Capacity Fade":
                d = df[df["battery_id"].astype(str)==bid].sort_values("cycle_index")
                if not d.empty:
                    ax.plot(d["cycle_index"], d["capacity"], color=c, lw=1.5, label=bid)
            else:
                if RUL_COL and not u_df.empty and "battery_id" in u_df.columns:
                    d = u_df[u_df["battery_id"].astype(str)==bid].sort_values("cycle_index")
                    if not d.empty:
                        ax.plot(d["cycle_index"], pd.to_numeric(d[RUL_COL],errors="coerce"),
                                color=c, lw=1.5, label=bid)

        if mode == "Capacity Fade":
            ax.axhline(1.6, color="#C0392B", lw=1.5, ls="--", label="EOL (1.6 Ah)")
            ax.set_ylabel("Capacity (Ah)")
        else:
            ax.axhline(0, color="#C0392B", lw=1, ls=":", alpha=0.5)
            ax.set_ylabel("Predicted RUL (cycles)")
            ax.set_ylim(bottom=0)

        patches = [mpatches.Patch(color=c, label=f"{g} — {GROUP_LABEL[g]}")
                   for g,c in GROUP_COLOR.items()]
        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles=handles+patches, fontsize=7, ncol=2)
        ax.set_xlabel("Cycle"); ax.set_title(f"{mode} — Selected Batteries")
        ax.grid(alpha=0.3); ax.spines[["top","right"]].set_visible(False)
        st.pyplot(fig); plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# 5 · RISK DISTRIBUTION
# ══════════════════════════════════════════════════════════════════════════════
elif section == SECTIONS[4]:
    st.title("⚠️ Risk Distribution")
    st.markdown(
        "For every cycle of every battery, the system calculates the probability of failure "
        "within the next **20 cycles** and assigns a risk category. "
        "Thresholds: **HIGH > 70%**, **MEDIUM 30–70%**, **LOW < 30%**."
    )

    risk_dist = unc_metrics.get("risk_distribution", {})
    if risk_dist:
        total = sum(risk_dist.values())
        col1, col2 = st.columns(2)
        with col1:
            fig, ax = plt.subplots(figsize=(5,5))
            labels = [f"{k}\n{v} rows" for k,v in risk_dist.items()]
            colors = {"LOW":"#2E8648","MEDIUM":"#E68A00","HIGH":"#C0392B"}
            clrs   = [colors[k] for k in risk_dist]
            wedges, _, autotexts = ax.pie(
                risk_dist.values(), labels=labels, colors=clrs,
                autopct="%1.1f%%", startangle=140, explode=[0.02]*3,
                textprops={"fontsize":10}
            )
            for at in autotexts:
                at.set_fontsize(10); at.set_color("white"); at.set_fontweight("bold")
            ax.set_title("Risk Category Distribution\n(all 2,790 observations)")
            st.pyplot(fig); plt.close(fig)
        with col2:
            st.markdown("#### Interpretation")
            for cat, color in [("HIGH","#C0392B"),("MEDIUM","#E68A00"),("LOW","#2E8648")]:
                n   = risk_dist.get(cat, 0)
                pct = 100*n/total if total else 0
                st.markdown(
                    f"<div style='background:{color}22;border-left:5px solid {color};"
                    f"padding:12px 16px;border-radius:5px;margin-bottom:10px'>"
                    f"<b style='color:{color};font-size:1.1em'>{cat}</b><br>"
                    f"<span style='font-size:1.8em;font-weight:700'>{n}</span> "
                    f"rows ({pct:.1f}%)</div>",
                    unsafe_allow_html=True,
                )
            st.markdown(
                f"**Mean predicted RUL:** {unc_metrics.get('mean_rul_prediction',0):.1f} cycles\n\n"
                f"**Mean interval width:** {unc_metrics.get('mean_uncertainty_width',0):.1f} cycles"
            )

    st.markdown("---")

    # Per-battery risk breakdown
    st.subheader("Risk Breakdown per Test Battery")
    if not u_df.empty and "battery_id" in u_df.columns and "risk_category" in u_df.columns:
        test_bats = metrics.get("split_metadata",{}).get("test_batteries",[])
        u_test = u_df[u_df["battery_id"].astype(str).isin([str(b) for b in test_bats])]
        if not u_test.empty:
            rows = []
            for bid in test_bats:
                sub = u_test[u_test["battery_id"].astype(str)==str(bid)]
                if sub.empty: continue
                rc = sub["risk_category"].value_counts().to_dict()
                rows.append({"Battery": str(bid),
                             "Temp Group": GROUP_LABEL[temp_group(str(bid))],
                             "Total cycles": len(sub),
                             "LOW":    rc.get("LOW",0),
                             "MEDIUM": rc.get("MEDIUM",0),
                             "HIGH":   rc.get("HIGH",0)})
            if rows:
                rdf = pd.DataFrame(rows)
                fig, ax = plt.subplots(figsize=(9, 4))
                x   = np.arange(len(rdf))
                w   = 0.25
                ax.bar(x-w,   rdf["LOW"],    w, color="#2E8648", label="LOW",    edgecolor="white")
                ax.bar(x,     rdf["MEDIUM"], w, color="#E68A00", label="MEDIUM", edgecolor="white")
                ax.bar(x+w,   rdf["HIGH"],   w, color="#C0392B", label="HIGH",   edgecolor="white")
                ax.set_xticks(x); ax.set_xticklabels(rdf["Battery"])
                ax.set_ylabel("Cycle count"); ax.set_title("Risk category counts per test battery")
                ax.legend(); ax.grid(axis="y", alpha=0.3)
                ax.spines[["top","right"]].set_visible(False)
                st.pyplot(fig); plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# 6 · DRIFT MONITORING
# ══════════════════════════════════════════════════════════════════════════════
elif section == SECTIONS[5]:
    st.title("📡 Drift Monitoring — Population Stability Index (PSI)")
    st.markdown(
        "PSI measures how much the **test data distribution** differs from **training data**. "
        "High PSI means the model is being asked to predict data that looks different from what it trained on."
    )

    overall_drift = drift.get("overall_status","—")
    alerts        = drift.get("alerts",[])
    psi_data      = drift.get("per_feature_psi", {})

    d_color = "#C0392B" if overall_drift=="RED" else "#E68A00" if overall_drift=="AMBER" else "#2E8648"
    st.markdown(
        f"<div style='background:{d_color}22;border-left:6px solid {d_color};"
        f"padding:14px 20px;border-radius:6px;margin-bottom:20px'>"
        f"<span style='font-size:1.2em;font-weight:700;color:{d_color}'>"
        f"Overall drift status: {overall_drift}</span></div>",
        unsafe_allow_html=True,
    )

    if psi_data:
        psi_df = pd.DataFrame([
            {"Feature": f, "PSI": round(v.get("psi",0),4), "Status": v.get("status","—")}
            for f,v in psi_data.items()
        ]).sort_values("PSI", ascending=True)

        col1, col2 = st.columns([3,2])
        with col1:
            fig, ax = plt.subplots(figsize=(7, 5))
            bar_colors = [
                "#C0392B" if s=="RED" else "#E68A00" if s=="AMBER" else "#2E8648"
                for s in psi_df["Status"]
            ]
            bars = ax.barh(psi_df["Feature"], psi_df["PSI"], color=bar_colors, edgecolor="white")
            ax.axvline(0.10, color="#E68A00", lw=1.5, ls="--", label="Amber (0.10)")
            ax.axvline(0.20, color="#C0392B", lw=1.5, ls="--", label="Red (0.20)")
            for b, v in zip(bars, psi_df["PSI"]):
                ax.text(v+0.02, b.get_y()+b.get_height()/2,
                        f"{v:.3f}", va="center", fontsize=9)
            ax.set_xlabel("PSI"); ax.set_title("Feature Drift: Train → Test")
            ax.legend(fontsize=9); ax.spines[["top","right"]].set_visible(False)
            ax.set_xlim(0, max(psi_df["PSI"])*1.2 + 0.3)
            st.pyplot(fig); plt.close(fig)
        with col2:
            st.markdown("#### Why RED?")
            st.markdown(
                "Our **test set includes 3 cold batteries** (B0041, B0044, B0052) "
                "tested at temperatures below 10°C.\n\n"
                "Training was mostly room-temperature batteries. "
                "Lower temperature changes voltage, current, and cycle duration — "
                "so PSI is high on those features.\n\n"
                "**This is expected, not a failure.** It confirms we need the temperature-stratified "
                "conformal calibration and LOBO to handle cold batteries correctly.\n\n"
                "**Degradation features** (capacity, ah_est, energy_j) also show high PSI because "
                "test batteries are at different stages of life — also expected."
            )
            if alerts:
                st.markdown("**Active alerts:**")
                for a in alerts:
                    st.markdown(f"- 🔴 {a}")


# ══════════════════════════════════════════════════════════════════════════════
# 7 · REASONING & HYPOTHESES
# ══════════════════════════════════════════════════════════════════════════════
elif section == SECTIONS[6]:
    st.title("💡 Reasoning & Hypotheses")
    st.markdown(
        "Stage 5 generates human-readable explanations grounded in model behaviour. "
        "All outputs are **hypotheses**, not proven causal claims."
    )

    tab1, tab2 = st.tabs(["Degradation Hypotheses", "Counterfactual Examples"])

    with tab1:
        st.subheader(f"{len(hypotheses)} Degradation Hypotheses")
        st.caption("Each hypothesis is derived from XGBoost feature importance. "
                   "Higher confidence = stronger model signal.")
        if hypotheses:
            for h in sorted(hypotheses, key=lambda x: x.get("confidence",0), reverse=True):
                conf = h.get("confidence",0)
                bar  = int(conf * 20)
                c    = "#2E8648" if conf > 0.2 else "#E68A00" if conf > 0.1 else "#AAAAAA"
                st.markdown(
                    f"<div style='border-left:4px solid {c};padding:10px 16px;"
                    f"background:{c}11;border-radius:4px;margin-bottom:10px'>"
                    f"<b style='color:{c}'>{h.get('hypothesis_id','')}</b> — "
                    f"<span style='font-size:1.05em'>{h.get('hypothesis_text','')}</span><br>"
                    f"<small style='color:#666'>Evidence: {h.get('supporting_evidence','')} | "
                    f"Confidence: {conf:.3f} {'█'*bar}{'░'*(20-bar)}</small>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    with tab2:
        st.subheader(f"{len(counterfact)} Counterfactual Examples")
        st.markdown(
            "A counterfactual answers: *'if this feature had been different, "
            "how would the predicted RUL have changed?'*"
        )
        if counterfact:
            cdf = pd.DataFrame([{
                "Observation":  c.get("observation_id",""),
                "True RUL":     c.get("actual_rul",""),
                "Predicted RUL":round(float(c.get("predicted_rul",0)),1),
                "Feature changed": c.get("counterfactual",{}).get("feature_changed",""),
                "Original value":  round(float(c.get("counterfactual",{}).get("original_value",0)),3),
                "New value":       round(float(c.get("counterfactual",{}).get("counterfactual_value",0)),3),
                "RUL change":      round(float(c.get("counterfactual",{}).get("predicted_rul_change",0)),2),
            } for c in counterfact])

            def color_change(val):
                try:
                    v = float(val)
                    return "color: #2E8648; font-weight:bold" if v>0 else \
                           "color: #C0392B; font-weight:bold" if v<0 else ""
                except: return ""
            st.dataframe(
                cdf.style.applymap(color_change, subset=["RUL change"]),
                use_container_width=True, hide_index=True,
            )
            st.caption("Green RUL change = if that feature were higher/lower, battery would last longer.")


# ══════════════════════════════════════════════════════════════════════════════
# 8 · FINAL REPORT
# ══════════════════════════════════════════════════════════════════════════════
elif section == SECTIONS[7]:
    st.title("📋 Final System Report")
    st.markdown(
        "This report is generated automatically by the Stage 6 Supervisor. "
        "It audits every pipeline output and issues the final verdict."
    )
    if report_path.exists():
        st.markdown(report_path.read_text(encoding="utf-8"))
    else:
        st.warning("final_system_report.md not found.")

    st.markdown("---")
    st.subheader("Artifact Checklist")
    artifacts = [
        ("cycle_features_with_rul.csv",       BASE/"data/processed/cycle_features_with_rul.csv"),
        ("uncertainty_estimates.json",         MDL/"uncertainty_estimates.json"),
        ("conformal_coverage_report.json",     MDL/"conformal_coverage_report.json"),
        ("survival_risk_predictions.csv",      MDL/"survival_risk_predictions.csv"),
        ("anomalies.json",                     MDL/"anomalies.json"),
        ("degradation_hypotheses.json",        MDL/"degradation_hypotheses.json"),
        ("counterfactual_examples.json",       MDL/"counterfactual_examples.json"),
        ("feature_importance.json",            MDL/"feature_importance.json"),
        ("groupkfold_cv_report.json",          MDL/"groupkfold_cv_report.json"),
        ("drift_report.json",                  MDL/"drift_report.json"),
        ("final_system_report.md",             MDL/"final_system_report.md"),
        ("conformal_calibrator.json",          TM/"conformal_calibrator.json"),
        ("model_metrics.json",                 TM/"model_metrics.json"),
        ("conformal_ablation.json",            TM/"conformal_ablation.json"),
    ]
    rows = [{"Artifact": name, "Exists": "✅  Yes" if Path(path).exists() else "❌  Missing"}
            for name, path in artifacts]
    adf = pd.DataFrame(rows)
    def color_exists(val):
        return "color: #2E8648; font-weight:bold" if "Yes" in str(val) \
               else "color: #C0392B; font-weight:bold"
    st.dataframe(adf.style.applymap(color_exists, subset=["Exists"]),
                 use_container_width=True, hide_index=True)
