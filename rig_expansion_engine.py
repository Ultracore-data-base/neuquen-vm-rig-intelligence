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


def _bucket(score):
    score = _num(score)
    if score >= 85:
        return "A / Expansion Target"
    if score >= 70:
        return "B / High Potential"
    if score >= 55:
        return "C / Monitor"
    if score >= 40:
        return "D / Early Signal"
    return "Low"


def _timing(score, gap):
    score = _num(score)
    gap = _num(gap)
    if score >= 85 and gap >= 2:
        return "0-6 months"
    if score >= 70 and gap >= 1:
        return "6-12 months"
    if score >= 55:
        return "12-24 months"
    return "Monitor"


def _maturity_penalty(observed_score, estimated_gap, market_intent):
    observed_score = _num(observed_score)
    estimated_gap = _num(estimated_gap)
    market_intent = _num(market_intent)

    if observed_score >= 85 and estimated_gap <= 0:
        return 30

    if observed_score >= 85 and market_intent >= 80 and estimated_gap <= 1:
        return 15

    return 0


def build_rig_expansion_score(scored, observed_activity, tender_probability):
    if scored is None or scored.empty:
        return pd.DataFrame()

    df = scored.copy()

    for col in ["area", "operator", "detected_basin", "basin", "province", "rig_demand_score"]:
        if col not in df.columns:
            df[col] = ""

    df["market_intent_score"] = pd.to_numeric(df["rig_demand_score"], errors="coerce").fillna(0)

    df["_area_key"] = df["area"].apply(_norm)
    df["_operator_key"] = df["operator"].apply(_norm)

    observed = observed_activity.copy() if observed_activity is not None else pd.DataFrame()

    if not observed.empty and "area" in observed.columns:
        observed["_area_key"] = observed["area"].apply(_norm)
        observed["_operator_key"] = observed["operator"].apply(_norm) if "operator" in observed.columns else ""

        obs_cols = [
            "_area_key",
            "_operator_key",
            "operational_observed_score",
            "drilling_signal",
            "trend_signal",
        ]
        obs_cols = [c for c in obs_cols if c in observed.columns]

        df = df.merge(
            observed[obs_cols].drop_duplicates(["_area_key", "_operator_key"]),
            on=["_area_key", "_operator_key"],
            how="left"
        )

    for col in ["operational_observed_score", "drilling_signal", "trend_signal"]:
        if col not in df.columns:
            df[col] = 0

    tender = tender_probability.copy() if tender_probability is not None else pd.DataFrame()

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
        "drilling_signal",
        "trend_signal",
        "Tender Probability (%)",
        "Estimated Gap",
        "CAPEX Signal",
    ]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["maturity_penalty"] = df.apply(
        lambda r: _maturity_penalty(
            r.get("operational_observed_score"),
            r.get("Estimated Gap"),
            r.get("market_intent_score"),
        ),
        axis=1
    )

    df["rig_expansion_score"] = (
        df["market_intent_score"] * 0.30
        + df["Tender Probability (%)"] * 0.20
        + df["CAPEX Signal"] * 0.20
        + df["drilling_signal"] * 0.15
        + df["trend_signal"] * 0.10
        + df["Estimated Gap"].clip(upper=4) * 5
        - df["maturity_penalty"]
    ).round(0)

    df["rig_expansion_score"] = df["rig_expansion_score"].clip(lower=0, upper=100).astype(int)
    df["rig_expansion_bucket"] = df["rig_expansion_score"].apply(_bucket)
    df["rig_expansion_timing"] = df.apply(
        lambda r: _timing(r.get("rig_expansion_score"), r.get("Estimated Gap")),
        axis=1
    )

    df["commercial_note"] = df.apply(
        lambda r: "Mature/high-activity asset: prioritize services over new rigs"
        if _num(r.get("operational_observed_score")) >= 85 and _num(r.get("Estimated Gap")) <= 0
        else "Potential new rig expansion target",
        axis=1
    )

    result = pd.DataFrame({
        "Area": df["area"],
        "Operator": df["operator"],
        "Basin": df.get("detected_basin", df.get("basin", "")),
        "Province": df.get("province", ""),
        "Rig Expansion Score": df["rig_expansion_score"],
        "Expansion Bucket": df["rig_expansion_bucket"],
        "Expected Timing": df["rig_expansion_timing"],
        "Market Intent": df["market_intent_score"].round(0).astype(int),
        "Observed Activity": df["operational_observed_score"].round(0).astype(int),
        "Tender Probability (%)": df["Tender Probability (%)"].round(0).astype(int),
        "Estimated Gap": df["Estimated Gap"].round(0).astype(int),
        "Drilling Signal": df["drilling_signal"].round(0).astype(int),
        "Trend Signal": df["trend_signal"].round(0).astype(int),
        "Maturity Penalty": df["maturity_penalty"].round(0).astype(int),
        "Commercial Note": df["commercial_note"],
    })

    return result.sort_values(
        ["Rig Expansion Score", "Estimated Gap", "Market Intent"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def rig_expansion_context_for_area(area, operator, rig_expansion_df):
    if rig_expansion_df is None or rig_expansion_df.empty:
        return None

    df = rig_expansion_df.copy()

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


def rig_expansion_html(area, operator, rig_expansion_df):
    info = rig_expansion_context_for_area(area, operator, rig_expansion_df)

    if not info:
        return """
        <div class="detail-row"><span>Rig Expansion</span><span>To verify</span></div>
        <div class="detail-row"><span>Timing</span><span>-</span></div>
        <div class="detail-row"><span>Bucket</span><span>-</span></div>
        """

    return f"""
    <div class="detail-row"><span>Rig Expansion</span><span>{info.get("Rig Expansion Score", "-")}</span></div>
    <div class="detail-row"><span>Bucket</span><span>{info.get("Expansion Bucket", "-")}</span></div>
    <div class="detail-row"><span>Timing</span><span>{info.get("Expected Timing", "-")}</span></div>
    <div class="detail-row"><span>Maturity Penalty</span><span>{info.get("Maturity Penalty", "-")}</span></div>
    <div class="detail-row"><span>Commercial Note</span><span>{info.get("Commercial Note", "-")}</span></div>
    """
