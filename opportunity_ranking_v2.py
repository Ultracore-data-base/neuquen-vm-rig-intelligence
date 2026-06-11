import pandas as pd


def normalize_text(value):
    return str(value or "").strip().upper().replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")


def parse_forecast_max(forecast_text):
    text = str(forecast_text or "").lower().replace("–", "-").replace("—", "-")

    if "2-4" in text or "2 - 4" in text:
        return 4
    if "1-3" in text or "1 - 3" in text:
        return 3
    if "1-2" in text or "1 - 2" in text:
        return 2
    if "watchlist" in text:
        return 1
    if "low" in text:
        return 0

    return 0


def safe_int(value):
    try:
        if pd.isna(value):
            return None
        return int(float(value))
    except Exception:
        return None


def build_alias_map(operator_aliases):
    alias_map = {}

    if operator_aliases is None or operator_aliases.empty:
        return alias_map

    required = {"operator_name", "operator_key"}
    if not required.issubset(operator_aliases.columns):
        return alias_map

    for _, row in operator_aliases.iterrows():
        alias = normalize_text(row.get("operator_name", ""))
        key = normalize_text(row.get("operator_key", ""))
        if alias and key:
            alias_map[alias] = key

    return alias_map


def operator_key(value, alias_map):
    text = normalize_text(value)

    if text in alias_map:
        return alias_map[text]

    # fallback fuzzy contains
    for alias, key in alias_map.items():
        if alias in text or text in alias:
            return key

    return text


def opportunity_priority(score, forecast_max, current_rigs):
    score = float(score or 0)

    if current_rigs is None:
        if score >= 85 and forecast_max >= 3:
            return "High Priority Verification"
        if score >= 70:
            return "Intelligence Required"
        return "Watchlist"

    gap = forecast_max - current_rigs

    if gap >= 2 and score >= 80:
        return "Open Rig Opportunity"
    if gap >= 1 and score >= 70:
        return "Potential Incremental Rig"
    if gap <= 0:
        return "Covered / Monitor Renewal"

    return "Watchlist"


def tender_probability(score, forecast_max, current_rigs, current_contractor):
    score = float(score or 0)
    contractor = normalize_text(current_contractor)

    if current_rigs is None:
        base = 45
        if score >= 90:
            base += 30
        elif score >= 80:
            base += 20
        elif score >= 70:
            base += 10

        if forecast_max >= 4:
            base += 15
        elif forecast_max >= 3:
            base += 10

        return min(base, 95)

    gap = forecast_max - current_rigs

    if gap >= 2:
        return min(65 + int(score / 5), 95)
    if gap == 1:
        return min(45 + int(score / 6), 80)
    if gap <= 0:
        if contractor in {"TO VERIFY", "UNKNOWN", "NONE", ""}:
            return 45
        return 20

    return 35


def tender_window(score, forecast_max, current_rigs):
    score = float(score or 0)

    if current_rigs is None:
        if score >= 85 and forecast_max >= 3:
            return "0-6 months"
        if score >= 70:
            return "6-12 months"
        return "12+ months"

    gap = forecast_max - current_rigs

    if gap >= 2:
        return "0-6 months"
    if gap == 1:
        return "6-12 months"
    return "Monitor renewal"


def stamper_fit(score, rig_type, current_rigs):
    score = float(score or 0)
    rig = normalize_text(rig_type)

    if "1500" in rig and "WALKING" in rig:
        if current_rigs is None:
            return "Excellent - verify access"
        return "Excellent technical match"

    if score >= 85:
        return "Excellent demand match"

    if score >= 70:
        return "Good fit"

    return "Watchlist"


def target_priority(commercial_priority, probability):
    if commercial_priority in {"Open Rig Opportunity", "High Priority Verification"} and probability >= 80:
        return "A"
    if probability >= 60:
        return "B"
    if probability >= 40:
        return "C"
    return "Monitor"


def build_opportunity_ranking_v2(scored, contractor_intelligence, forecast_func, operator_aliases=None):
    if scored is None or scored.empty:
        return pd.DataFrame()

    alias_map = build_alias_map(operator_aliases)

    df = scored.copy()

    if "rig_demand_score" not in df.columns:
        df["rig_demand_score"] = 0

    df["rig_demand_score"] = pd.to_numeric(df["rig_demand_score"], errors="coerce").fillna(0)
    df["Rig Forecast"] = df["rig_demand_score"].apply(forecast_func)
    df["forecast_max"] = df["Rig Forecast"].apply(parse_forecast_max)
    df["operator_key"] = df["operator"].apply(lambda x: operator_key(x, alias_map))

    if contractor_intelligence is not None and not contractor_intelligence.empty:
        cdf = contractor_intelligence.copy()
        cdf["operator_key"] = cdf["operator"].apply(lambda x: operator_key(x, alias_map))
        cdf["rig_count"] = pd.to_numeric(cdf["rig_count"], errors="coerce")

        cdf = cdf[
            ["operator_key", "current_contractor", "contract_type", "rig_type", "rig_count"]
        ].drop_duplicates("operator_key")

        df = df.merge(cdf, on="operator_key", how="left")
    else:
        df["current_contractor"] = None
        df["contract_type"] = None
        df["rig_type"] = None
        df["rig_count"] = None

    df["current_rigs_int"] = df["rig_count"].apply(safe_int)
    df["Estimated Gap"] = df.apply(
        lambda row: "To verify" if row["current_rigs_int"] is None else max(row["forecast_max"] - row["current_rigs_int"], 0),
        axis=1,
    )

    df["Commercial Priority"] = df.apply(
        lambda row: opportunity_priority(
            row["rig_demand_score"],
            row["forecast_max"],
            row["current_rigs_int"],
        ),
        axis=1,
    )

    df["Tender Probability (%)"] = df.apply(
        lambda row: tender_probability(
            row["rig_demand_score"],
            row["forecast_max"],
            row["current_rigs_int"],
            row.get("current_contractor", ""),
        ),
        axis=1,
    )

    df["Tender Window"] = df.apply(
        lambda row: tender_window(
            row["rig_demand_score"],
            row["forecast_max"],
            row["current_rigs_int"],
        ),
        axis=1,
    )

    df["Stamper Fit"] = df.apply(
        lambda row: stamper_fit(
            row["rig_demand_score"],
            row.get("rig_type", ""),
            row["current_rigs_int"],
        ),
        axis=1,
    )

    df["Target Priority"] = df.apply(
        lambda row: target_priority(
            row["Commercial Priority"],
            row["Tender Probability (%)"],
        ),
        axis=1,
    )

    result = pd.DataFrame({
        "Target Priority": df["Target Priority"],
        "Area": df.get("area", ""),
        "Operator": df.get("operator", ""),
        "Basin": df.get("detected_basin", df.get("basin", "")),
        "Province": df.get("province", ""),
        "Drill Score": df["rig_demand_score"],
        "Rig Forecast": df["Rig Forecast"],
        "Current Contractor": df.get("current_contractor", "").fillna("To verify"),
        "Contract Type": df.get("contract_type", "").fillna("Unknown"),
        "Rig Type": df.get("rig_type", "").fillna("Unknown"),
        "Current Rigs": df.get("rig_count", "").fillna("To verify"),
        "Estimated Gap": df["Estimated Gap"],
        "Commercial Priority": df["Commercial Priority"],
        "Tender Probability (%)": df["Tender Probability (%)"],
        "Tender Window": df["Tender Window"],
        "Stamper Fit": df["Stamper Fit"],
    })

    priority_order = {
        "A": 1,
        "B": 2,
        "C": 3,
        "Monitor": 4,
    }

    result["_priority_rank"] = result["Target Priority"].map(priority_order).fillna(99)
    result = result.sort_values(
        ["_priority_rank", "Tender Probability (%)", "Drill Score"],
        ascending=[True, False, False],
    ).drop(columns=["_priority_rank"])

    return result.reset_index(drop=True)
