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


def _forecast_max(text):
    text = str(text or "").lower().replace("–", "-").replace("—", "-")
    if "2-4" in text or "2 - 4" in text:
        return 4
    if "1-3" in text or "1 - 3" in text:
        return 3
    if "1-2" in text or "1 - 2" in text:
        return 2
    if "watchlist" in text:
        return 1
    return 0


def _priority(probability):
    probability = _num(probability)
    if probability >= 85:
        return "Tier 1"
    if probability >= 70:
        return "Tier 2"
    if probability >= 55:
        return "Tier 3"
    return "Monitor"


def _timing(probability, gap):
    probability = _num(probability)
    gap = _num(gap)
    if probability >= 85 and gap >= 2:
        return "0-6 months"
    if probability >= 70 and gap >= 1:
        return "6-12 months"
    if probability >= 55:
        return "12-18 months"
    return "Monitor"


def _confidence(market_score, observed_score, gap_score):
    values = [_num(market_score), _num(observed_score), _num(gap_score)]
    spread = max(values) - min(values)
    avg = sum(values) / len(values)

    if avg >= 75 and spread <= 25:
        return "High"
    if avg >= 60:
        return "Medium"
    return "Low"


def _get_observed(area, operator, observed_activity):
    if observed_activity is None or observed_activity.empty:
        return 0

    df = observed_activity.copy()
    if "area" not in df.columns:
        return 0

    df["_area_key"] = df["area"].apply(_norm)
    match = df[df["_area_key"] == _norm(area)]

    if not match.empty and operator and "operator" in df.columns:
        match["_operator_key"] = match["operator"].apply(_norm)
        exact = match[match["_operator_key"] == _norm(operator)]
        if not exact.empty:
            match = exact

    if match.empty:
        return 0

    row = match.iloc[0]
    return _num(row.get("operational_observed_score", row.get("observed_score", 0)))


def _get_current_rigs(operator, contractor_intelligence):
    if contractor_intelligence is None or contractor_intelligence.empty:
        return 0

    df = contractor_intelligence.copy()
    if "operator" not in df.columns:
        return 0

    df["_operator_key"] = df["operator"].apply(_norm)
    match = df[df["_operator_key"] == _norm(operator)]

    if match.empty:
        return 0

    return _num(match.iloc[0].get("rig_count", 0))


def build_tender_probability(scored, observed_activity, contractor_intelligence, forecast_func):
    if scored is None or scored.empty:
        return pd.DataFrame()

    df = scored.copy()

    for col in ["area", "operator", "detected_basin", "basin", "province", "rig_demand_score"]:
        if col not in df.columns:
            df[col] = ""

    df["market_intent_score"] = pd.to_numeric(df["rig_demand_score"], errors="coerce").fillna(0)
    df["rig_forecast"] = df["market_intent_score"].apply(forecast_func)
    df["forecast_max"] = df["rig_forecast"].apply(_forecast_max)

    df["observed_activity_score"] = df.apply(
        lambda r: _get_observed(r.get("area", ""), r.get("operator", ""), observed_activity),
        axis=1
    )

    df["current_rigs"] = df["operator"].apply(
        lambda op: _get_current_rigs(op, contractor_intelligence)
    )

    df["estimated_gap"] = (df["forecast_max"] - df["current_rigs"]).clip(lower=0)

    df["contractor_gap_score"] = df["estimated_gap"].apply(
        lambda gap: min(100, gap * 25)
    )

    # Temporary CAPEX proxy until real CAPEX guidance is parsed:
    # high market intent + high observed activity indicates likely capital program.
    df["capex_signal_score"] = (
        df["market_intent_score"] * 0.60
        + df["observed_activity_score"] * 0.40
    ).round(0)

    df["tender_probability"] = (
        df["market_intent_score"] * 0.25
        + df["observed_activity_score"] * 0.25
        + df["market_intent_score"] * 0.20
        + df["contractor_gap_score"] * 0.15
        + df["capex_signal_score"] * 0.15
    ).round(0)

    # If there is no estimated gap, reduce tender probability materially,
    # because high activity may already be fully covered.
    df.loc[df["estimated_gap"] <= 0, "tender_probability"] = (
        df.loc[df["estimated_gap"] <= 0, "tender_probability"] * 0.55
    ).round(0)

    df["tender_probability"] = df["tender_probability"].clip(lower=0, upper=100).astype(int)

    df["tender_confidence"] = df.apply(
        lambda r: _confidence(
            r.get("market_intent_score"),
            r.get("observed_activity_score"),
            r.get("contractor_gap_score"),
        ),
        axis=1
    )

    df["expected_timing"] = df.apply(
        lambda r: _timing(r.get("tender_probability"), r.get("estimated_gap")),
        axis=1
    )

    df["tender_priority"] = df["tender_probability"].apply(_priority)

    result = pd.DataFrame({
        "Area": df["area"],
        "Operator": df["operator"],
        "Basin": df.get("detected_basin", df.get("basin", "")),
        "Province": df.get("province", ""),
        "Market Intent": df["market_intent_score"].round(0).astype(int),
        "Observed Activity": df["observed_activity_score"].round(0).astype(int),
        "Rig Forecast": df["rig_forecast"],
        "Current Rigs": df["current_rigs"].round(0).astype(int),
        "Estimated Gap": df["estimated_gap"].round(0).astype(int),
        "Contractor Gap Score": df["contractor_gap_score"].round(0).astype(int),
        "CAPEX Signal": df["capex_signal_score"].round(0).astype(int),
        "Tender Probability (%)": df["tender_probability"],
        "Confidence": df["tender_confidence"],
        "Expected Timing": df["expected_timing"],
        "Priority": df["tender_priority"],
    })

    return result.sort_values(
        ["Tender Probability (%)", "Observed Activity", "Market Intent"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def tender_context_for_area(area, operator, tender_df):
    if tender_df is None or tender_df.empty:
        return None

    df = tender_df.copy()

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


def tender_probability_html(area, operator, tender_df):
    info = tender_context_for_area(area, operator, tender_df)

    if not info:
        return """
        <div class="detail-row"><span>Tender Probability</span><span>To verify</span></div>
        <div class="detail-row"><span>Confidence</span><span>-</span></div>
        <div class="detail-row"><span>Expected Timing</span><span>-</span></div>
        <div class="detail-row"><span>Priority</span><span>-</span></div>
        """

    return f"""
    <div class="detail-row"><span>Tender Probability</span><span>{info.get("Tender Probability (%)", "-")}%</span></div>
    <div class="detail-row"><span>Confidence</span><span>{info.get("Confidence", "-")}</span></div>
    <div class="detail-row"><span>Expected Timing</span><span>{info.get("Expected Timing", "-")}</span></div>
    <div class="detail-row"><span>Priority</span><span>{info.get("Priority", "-")}</span></div>
    <div class="detail-row"><span>Estimated Gap</span><span>{info.get("Estimated Gap", "-")}</span></div>
    """
