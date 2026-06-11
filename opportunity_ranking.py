import pandas as pd


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
        return int(float(value))
    except Exception:
        return None


def normalize_operator(value):
    return str(value or "").strip().upper()


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


def build_opportunity_ranking(scored, contractor_intelligence, forecast_func):
    if scored is None or scored.empty:
        return pd.DataFrame()

    df = scored.copy()

    if "rig_demand_score" not in df.columns:
        df["rig_demand_score"] = 0

    df["rig_demand_score"] = pd.to_numeric(df["rig_demand_score"], errors="coerce").fillna(0)
    df["rig_forecast"] = df["rig_demand_score"].apply(forecast_func)
    df["forecast_max"] = df["rig_forecast"].apply(parse_forecast_max)

    df["operator_norm"] = df["operator"].apply(normalize_operator)

    if contractor_intelligence is not None and not contractor_intelligence.empty:
        contractor_df = contractor_intelligence.copy()
        contractor_df["operator_norm"] = contractor_df["operator"].apply(normalize_operator)
        contractor_df["rig_count"] = pd.to_numeric(contractor_df["rig_count"], errors="coerce")

        contractor_df = contractor_df[
            ["operator_norm", "current_contractor", "contract_type", "rig_type", "rig_count"]
        ].drop_duplicates("operator_norm")

        df = df.merge(contractor_df, on="operator_norm", how="left")
    else:
        df["current_contractor"] = "To verify"
        df["contract_type"] = "Unknown"
        df["rig_type"] = "Unknown"
        df["rig_count"] = None

    df["current_rigs"] = df["rig_count"].apply(safe_int)
    df["estimated_gap"] = df.apply(
        lambda row: "To verify" if row["current_rigs"] is None else max(row["forecast_max"] - row["current_rigs"], 0),
        axis=1
    )

    df["commercial_priority"] = df.apply(
        lambda row: opportunity_priority(
            row["rig_demand_score"],
            row["forecast_max"],
            row["current_rigs"],
        ),
        axis=1
    )

    keep = [
        "area",
        "operator",
        "detected_basin",
        "province",
        "rig_demand_score",
        "rig_forecast",
        "current_contractor",
        "contract_type",
        "rig_type",
        "current_rigs",
        "estimated_gap",
        "commercial_priority",
    ]

    for col in keep:
        if col not in df.columns:
            df[col] = ""

    result = df[keep].copy()

    result = result.rename(columns={
        "area": "Area",
        "operator": "Operator",
        "detected_basin": "Basin",
        "province": "Province",
        "rig_demand_score": "Drill Score",
        "rig_forecast": "Rig Forecast",
        "current_contractor": "Current Contractor",
        "contract_type": "Contract Type",
        "rig_type": "Rig Type",
        "current_rigs": "Current Rigs",
        "estimated_gap": "Estimated Gap",
        "commercial_priority": "Commercial Priority",
    })

    priority_order = {
        "Open Rig Opportunity": 1,
        "High Priority Verification": 2,
        "Potential Incremental Rig": 3,
        "Intelligence Required": 4,
        "Covered / Monitor Renewal": 5,
        "Watchlist": 6,
    }

    result["_priority_rank"] = result["Commercial Priority"].map(priority_order).fillna(99)
    result = result.sort_values(
        ["_priority_rank", "Drill Score"],
        ascending=[True, False]
    ).drop(columns=["_priority_rank"])

    return result.reset_index(drop=True)
