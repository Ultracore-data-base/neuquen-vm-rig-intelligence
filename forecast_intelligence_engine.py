import pandas as pd


def _norm(value):
    return str(value or "").strip().upper()


def _num(value, default=0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _trend(delta):
    delta = _num(delta)
    if delta >= 10:
        return "Strong Rising"
    if delta >= 5:
        return "Rising"
    if delta >= -4:
        return "Stable"
    if delta >= -10:
        return "Softening"
    return "Declining"


def _priority(score):
    score = _num(score)
    if score >= 85:
        return "A / Immediate"
    if score >= 70:
        return "B / High"
    if score >= 55:
        return "C / Monitor"
    return "D / Watchlist"


def build_forecast_intelligence(scored, observed_activity, tender_probability):
    if scored is None or scored.empty:
        return pd.DataFrame()

    df = scored.copy()

    for col in ["area", "operator", "detected_basin", "basin", "province", "rig_demand_score"]:
        if col not in df.columns:
            df[col] = ""

    df["market_intent_score"] = pd.to_numeric(df["rig_demand_score"], errors="coerce").fillna(0)

    observed = observed_activity.copy() if observed_activity is not None else pd.DataFrame()
    tender = tender_probability.copy() if tender_probability is not None else pd.DataFrame()

    df["_area_key"] = df["area"].apply(_norm)
    df["_operator_key"] = df["operator"].apply(_norm)

    if not observed.empty and "area" in observed.columns:
        observed["_area_key"] = observed["area"].apply(_norm)
        observed["_operator_key"] = observed["operator"].apply(_norm) if "operator" in observed.columns else ""

        obs_cols = [
            "_area_key",
            "_operator_key",
            "operational_observed_score",
            "production_signal",
            "drilling_signal",
            "well_status_signal",
            "trend_signal",
        ]
        obs_cols = [c for c in obs_cols if c in observed.columns]

        df = df.merge(
            observed[obs_cols].drop_duplicates(["_area_key", "_operator_key"]),
            on=["_area_key", "_operator_key"],
            how="left"
        )

    if "operational_observed_score" not in df.columns:
        df["operational_observed_score"] = 0

    if not tender.empty and "Area" in tender.columns:
        tender["_area_key"] = tender["Area"].apply(_norm)
        tender["_operator_key"] = tender["Operator"].apply(_norm) if "Operator" in tender.columns else ""

        t_cols = [
            "_area_key",
            "_operator_key",
            "Tender Probability (%)",
            "Estimated Gap",
            "CAPEX Signal",
            "Expected Timing",
            "Priority",
        ]
        t_cols = [c for c in t_cols if c in tender.columns]

        df = df.merge(
            tender[t_cols].drop_duplicates(["_area_key", "_operator_key"]),
            on=["_area_key", "_operator_key"],
            how="left"
        )

    for col in [
        "operational_observed_score",
        "Tender Probability (%)",
        "Estimated Gap",
        "CAPEX Signal",
    ]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["forecast_activity_12m"] = (
        df["operational_observed_score"] * 0.35
        + df["market_intent_score"] * 0.30
        + df["Tender Probability (%)"] * 0.20
        + df["CAPEX Signal"] * 0.15
    ).round(0)

    df["forecast_activity_24m"] = (
        df["operational_observed_score"] * 0.25
        + df["market_intent_score"] * 0.35
        + df["Tender Probability (%)"] * 0.20
        + df["CAPEX Signal"] * 0.20
    ).round(0)

    df["delta_12m"] = (df["forecast_activity_12m"] - df["operational_observed_score"]).round(0)
    df["delta_24m"] = (df["forecast_activity_24m"] - df["operational_observed_score"]).round(0)

    df["rig_demand_trend"] = df["delta_12m"].apply(_trend)
    df["forecast_priority"] = df["forecast_activity_12m"].apply(_priority)

    result = pd.DataFrame({
        "Area": df["area"],
        "Operator": df["operator"],
        "Basin": df.get("detected_basin", df.get("basin", "")),
        "Province": df.get("province", ""),
        "Current Activity": df["operational_observed_score"].round(0).astype(int),
        "Market Intent": df["market_intent_score"].round(0).astype(int),
        "Tender Probability (%)": df["Tender Probability (%)"].round(0).astype(int),
        "Forecast Activity 12m": df["forecast_activity_12m"].round(0).astype(int),
        "Forecast Activity 24m": df["forecast_activity_24m"].round(0).astype(int),
        "Delta 12m": df["delta_12m"].round(0).astype(int),
        "Delta 24m": df["delta_24m"].round(0).astype(int),
        "Rig Demand Trend": df["rig_demand_trend"],
        "Forecast Priority": df["forecast_priority"],
        "Estimated Gap": df["Estimated Gap"].round(0).astype(int),
        "Expected Timing": df.get("Expected Timing", ""),
    })

    return result.sort_values(
        ["Forecast Activity 12m", "Delta 12m", "Tender Probability (%)"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def forecast_context_for_area(area, operator, forecast_df):
    if forecast_df is None or forecast_df.empty:
        return None

    df = forecast_df.copy()

    if "Area" not in df.columns:
        return None

    df["_area_key"] = df["Area"].apply(_norm)
    match = df[df["_area_key"] == _norm(area)]

    if not match.empty and operator and "Operator" in df.columns:
        match["_operator_key"] = match["Operator"].apply(_norm)
        exact = match[match["_operator_key"] == _norm(operator)]
        if not exact.empty:
            match = exact

    if match.empty:
        return None

    return match.iloc[0].to_dict()


def forecast_intelligence_html(area, operator, forecast_df):
    info = forecast_context_for_area(area, operator, forecast_df)

    if not info:
        return """
        <div class="detail-row"><span>Current Activity</span><span>To verify</span></div>
        <div class="detail-row"><span>Forecast 12m</span><span>-</span></div>
        <div class="detail-row"><span>Forecast 24m</span><span>-</span></div>
        <div class="detail-row"><span>Trend</span><span>-</span></div>
        """

    return f"""
    <div class="detail-row"><span>Current Activity</span><span>{info.get("Current Activity", "-")}</span></div>
    <div class="detail-row"><span>Forecast 12m</span><span>{info.get("Forecast Activity 12m", "-")}</span></div>
    <div class="detail-row"><span>Forecast 24m</span><span>{info.get("Forecast Activity 24m", "-")}</span></div>
    <div class="detail-row"><span>Delta 12m</span><span>{info.get("Delta 12m", "-")}</span></div>
    <div class="detail-row"><span>Trend</span><span>{info.get("Rig Demand Trend", "-")}</span></div>
    <div class="detail-row"><span>Priority</span><span>{info.get("Forecast Priority", "-")}</span></div>
    """
