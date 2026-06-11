import pandas as pd


def _norm(value):
    return str(value or "").strip().upper()


def _fmt(value, default="-"):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value)


def observed_activity_context_for_area(area, operator, observed_activity):
    if observed_activity is None or observed_activity.empty:
        return None

    df = observed_activity.copy()

    if "area" not in df.columns:
        return None

    area_key = _norm(area)
    operator_key = _norm(operator)

    df["_area_key"] = df["area"].apply(_norm)

    match = df[df["_area_key"] == area_key]

    if not match.empty and operator_key and "operator" in df.columns:
        match["_operator_key"] = match["operator"].apply(_norm)
        exact = match[match["_operator_key"] == operator_key]
        if not exact.empty:
            match = exact

    if match.empty:
        return None

    row = match.iloc[0].to_dict()

    return {
        "observed_score": row.get("operational_observed_score", row.get("observed_score", "-")),
        "production_signal": row.get("production_signal", "-"),
        "drilling_signal": row.get("drilling_signal", "-"),
        "well_status_signal": row.get("well_status_signal", "-"),
        "trend_signal": row.get("trend_signal", "-"),
        "activity_type": row.get("activity_type", "-"),
        "note": row.get("observed_activity_note", "-"),
    }


def observed_activity_html(area, operator, observed_activity):
    info = observed_activity_context_for_area(area, operator, observed_activity)

    if not info:
        return """
        <div class="detail-row"><span>Observed Score</span><span>To verify</span></div>
        <div class="detail-row"><span>Production Signal</span><span>-</span></div>
        <div class="detail-row"><span>Drilling Signal</span><span>-</span></div>
        <div class="detail-row"><span>Well Status</span><span>-</span></div>
        <div class="detail-row"><span>Trend Signal</span><span>-</span></div>
        """

    return f"""
    <div class="detail-row"><span>Observed Score</span><span>{_fmt(info.get("observed_score"))}</span></div>
    <div class="detail-row"><span>Production Signal</span><span>{_fmt(info.get("production_signal"))}</span></div>
    <div class="detail-row"><span>Drilling Signal</span><span>{_fmt(info.get("drilling_signal"))}</span></div>
    <div class="detail-row"><span>Well Status</span><span>{_fmt(info.get("well_status_signal"))}</span></div>
    <div class="detail-row"><span>Trend Signal</span><span>{_fmt(info.get("trend_signal"))}</span></div>
    <div class="detail-row"><span>Activity Type</span><span>{_fmt(info.get("activity_type"))}</span></div>
    """
