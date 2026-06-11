import pandas as pd


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
        return "A / Core"
    if score >= 70:
        return "B / Active"
    if score >= 55:
        return "C / Monitor"
    if score >= 40:
        return "D / Watchlist"
    return "Low"


def calculate_observed_activity(df):
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()

    for col in [
        "production_signal",
        "drilling_signal",
        "well_status_signal",
        "trend_signal",
    ]:
        if col not in out.columns:
            out[col] = 0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    out["operational_observed_score"] = (
        out["production_signal"] * 0.30
        + out["drilling_signal"] * 0.35
        + out["well_status_signal"] * 0.20
        + out["trend_signal"] * 0.15
    ).round(0).astype(int)

    out["observed_activity_bucket"] = out["operational_observed_score"].apply(_bucket)

    return out.sort_values(
        ["operational_observed_score", "drilling_signal", "production_signal"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def observed_activity_by_operator(df):
    if df is None or df.empty:
        return pd.DataFrame()

    calc = calculate_observed_activity(df)

    if "operator" not in calc.columns:
        return pd.DataFrame()

    summary = (
        calc.groupby("operator", dropna=False)
        .agg(
            areas=("area", "count"),
            avg_observed_score=("operational_observed_score", "mean"),
            max_observed_score=("operational_observed_score", "max"),
            avg_production=("production_signal", "mean"),
            avg_drilling=("drilling_signal", "mean"),
            avg_well_status=("well_status_signal", "mean"),
            avg_trend=("trend_signal", "mean"),
        )
        .reset_index()
    )

    for col in [
        "avg_observed_score",
        "avg_production",
        "avg_drilling",
        "avg_well_status",
        "avg_trend",
    ]:
        summary[col] = summary[col].round(1)

    summary["observed_activity_bucket"] = summary["avg_observed_score"].apply(_bucket)

    return summary.sort_values(
        ["avg_observed_score", "max_observed_score"],
        ascending=[False, False],
    ).reset_index(drop=True)


def observed_activity_by_area(df, n=30):
    if df is None or df.empty:
        return pd.DataFrame()

    calc = calculate_observed_activity(df)

    cols = [
        "area",
        "operator",
        "basin",
        "province",
        "operational_observed_score",
        "observed_activity_bucket",
        "production_signal",
        "drilling_signal",
        "well_status_signal",
        "trend_signal",
        "activity_type",
        "observed_activity_note",
    ]

    cols = [c for c in cols if c in calc.columns]
    return calc[cols].head(n).reset_index(drop=True)


def observed_score_for_area(df, area, operator=None):
    if df is None or df.empty:
        return None

    calc = calculate_observed_activity(df)

    if "area" not in calc.columns:
        return None

    mask = calc["area"].astype(str).str.upper().eq(str(area).upper())

    if operator and "operator" in calc.columns:
        mask = mask & calc["operator"].astype(str).str.upper().eq(str(operator).upper())

    subset = calc[mask]

    if subset.empty:
        return None

    row = subset.iloc[0].to_dict()

    return {
        "observed_score": row.get("operational_observed_score"),
        "bucket": row.get("observed_activity_bucket"),
        "production_signal": row.get("production_signal"),
        "drilling_signal": row.get("drilling_signal"),
        "well_status_signal": row.get("well_status_signal"),
        "trend_signal": row.get("trend_signal"),
        "note": row.get("observed_activity_note", ""),
    }
