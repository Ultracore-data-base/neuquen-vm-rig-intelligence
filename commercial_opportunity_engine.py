import pandas as pd

from contract_intelligence_engine import (
    months_remaining,
    expiry_opportunity_score
)


def _safe_float(value, default=0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value):
    try:
        if pd.isna(value):
            return None
        return int(float(value))
    except Exception:
        return None


def _norm(value):
    return str(value or "").strip().upper()


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


def tender_probability(score, forecast_text, rig_count, current_contractor):
    score = _safe_float(score, 0)
    forecast_max = parse_forecast_max(forecast_text)
    rigs = _safe_int(rig_count)
    contractor = _norm(current_contractor)

    if rigs is None:
        probability = 35
        if score >= 90:
            probability += 35
        elif score >= 80:
            probability += 25
        elif score >= 70:
            probability += 15

        if forecast_max >= 4:
            probability += 15
        elif forecast_max >= 3:
            probability += 10
        elif forecast_max >= 2:
            probability += 5

        return min(probability, 95)

    gap = forecast_max - rigs

    if gap >= 2:
        probability = 70 + min(int(score / 10), 10)
    elif gap == 1:
        probability = 55 + min(int(score / 12), 8)
    elif gap <= 0:
        probability = 25
        if contractor in ["TO VERIFY", "UNKNOWN", "NONE", ""]:
            probability += 15
    else:
        probability = 40

    return max(5, min(probability, 95))


def stamper_fit(score, forecast_text, rig_type, rig_count):
    score = _safe_float(score, 0)
    forecast_max = parse_forecast_max(forecast_text)
    rig = _norm(rig_type)
    rigs = _safe_int(rig_count)

    if "1500" in rig and "WALKING" in rig:
        return "A - Excellent technical fit"

    if score >= 85 and forecast_max >= 3:
        return "A - High demand fit"

    if score >= 75 and forecast_max >= 2:
        return "B - Good commercial fit"

    if rigs is None and score >= 70:
        return "B - Verify contractor coverage"

    return "C - Monitor"


def commercial_priority(score, probability, fit):
    score = _safe_float(score, 0)
    probability = _safe_float(probability, 0)
    fit = str(fit or "")

    if probability >= 80 and fit.startswith("A"):
        return "A"
    if probability >= 65:
        return "B"
    if probability >= 45 or score >= 70:
        return "C"
    return "Monitor"


def heat_score(probability, fit, estimated_gap):
    probability = _safe_float(probability, 0)

    fit_bonus = 0
    if str(fit).startswith("A"):
        fit_bonus = 15
    elif str(fit).startswith("B"):
        fit_bonus = 8

    if str(estimated_gap).lower() == "to verify":
        gap_bonus = 10
    else:
        gap = _safe_float(estimated_gap, 0)
        gap_bonus = min(gap * 10, 20)

    return min(round(probability + fit_bonus + gap_bonus), 100)


def heat_bucket(score):
    score = _safe_float(score, 0)
    if score >= 85:
        return "Very High"
    if score >= 70:
        return "High"
    if score >= 50:
        return "Medium"
    return "Low"

def contract_phase(months):
    if months is None:
        return "Unknown"

    if months <= 3:
        return "Active Rebid"

    if months <= 6:
        return "Renewal Window"

    if months <= 12:
        return "Prepare"

    return "Monitor"
    
    def next_action(months):

    if months is None:
        return "Monitor"

    if months <= 3:
        return "Submit quotation"

    if months <= 6:
        return "Prepare renewal proposal"

    if months <= 12:
        return "Engage drilling team"

    return "Relationship management"


def enrich_opportunity_ranking(opportunity_ranking):
    if opportunity_ranking is None or opportunity_ranking.empty:
        return pd.DataFrame()

    df = opportunity_ranking.copy()

    if "Contract Expiry" in df.columns:

    df["Months Remaining"] = df["Contract Expiry"].apply(
        lambda x: months_remaining(x)
    )

    df["Renewal Probability (%)"] = df["Months Remaining"].apply(
        lambda x: expiry_opportunity_score(x)
    )

    for col in ["Drill Score", "Rig Forecast", "Current Rigs", "Current Contractor", "Rig Type", "Estimated Gap"]:
        if col not in df.columns:
            df[col] = ""

    df["Tender Probability (%)"] = df.apply(
        lambda row: tender_probability(
            row.get("Drill Score", 0),
            row.get("Rig Forecast", ""),
            row.get("Current Rigs", None),
            row.get("Current Contractor", ""),
        ),
        axis=1,
    )

    df["Stamper Fit"] = df.apply(
        lambda row: stamper_fit(
            row.get("Drill Score", 0),
            row.get("Rig Forecast", ""),
            row.get("Rig Type", ""),
            row.get("Current Rigs", None),
        ),
        axis=1,
    )

    df["Target Priority"] = df.apply(
        lambda row: commercial_priority(
            row.get("Drill Score", 0),
            row.get("Tender Probability (%)", 0),
            row.get("Stamper Fit", ""),
        ),
        axis=1,
    )
    df["Next Action"] = df["Months Remaining"].apply(
    next_action
)
    df["Opportunity Heat Score"] = df.apply(
        lambda row: heat_score(
            row.get("Tender Probability (%)", 0),
            row.get("Stamper Fit", ""),
            row.get("Estimated Gap", 0),
        ),
        axis=1,
    )
    df["Contract Phase"] = df["Months Remaining"].apply(
    contract_phase
)

    df["Opportunity Heat"] = df["Opportunity Heat Score"].apply(heat_bucket)

    order = {"A": 1, "B": 2, "C": 3, "Monitor": 4}
    df["_rank"] = df["Target Priority"].map(order).fillna(99)
    df = df.sort_values(
        ["_rank", "Opportunity Heat Score", "Tender Probability (%)", "Drill Score"],
        ascending=[True, False, False, False],
    ).drop(columns=["_rank"])

    preferred = [
        "Target Priority",
        "Opportunity Heat",
        "Opportunity Heat Score",
        "Area",
        "Operator",
        "Basin",
        "Province",
        "Drill Score",
        "Rig Forecast",
        "Current Contractor",
        "Contract Type",
        "Rig Type",
        "Current Rigs",
        "Estimated Gap",
        "Commercial Priority",
        "Tender Probability (%)",
        "Stamper Fit",
    ]

    return "Monitor"

    cols = [c for c in preferred if c in df.columns] + [c for c in df.columns if c not in preferred]
    return df[cols].reset_index(drop=True)
