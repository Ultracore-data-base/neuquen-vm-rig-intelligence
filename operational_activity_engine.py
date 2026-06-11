import pandas as pd


def _safe_num(value, default=0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _bucket(score):
    score = _safe_num(score)
    if score >= 85:
        return "Very High"
    if score >= 70:
        return "High"
    if score >= 55:
        return "Medium"
    if score >= 40:
        return "Monitor"
    return "Low"


def calculate_operational_activity_score(df):
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()

    for col in [
        "drilling_score",
        "frac_score",
        "production_score",
        "seismic_score",
        "well_status_score",
    ]:
        if col not in out.columns:
            out[col] = 0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    out["operational_activity_score"] = (
        out["drilling_score"] * 0.40
        + out["frac_score"] * 0.20
        + out["production_score"] * 0.15
        + out["seismic_score"] * 0.10
        + out["well_status_score"] * 0.15
    ).round(0).astype(int)

    out["activity_bucket"] = out["operational_activity_score"].apply(_bucket)

    return out.sort_values(
        ["operational_activity_score", "drilling_score", "frac_score"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def activity_summary_by_operator(activity_df):
    if activity_df is None or activity_df.empty:
        return pd.DataFrame()

    df = calculate_operational_activity_score(activity_df)

    if "operator" not in df.columns:
        return pd.DataFrame()

    summary = (
        df.groupby("operator", dropna=False)
        .agg(
            areas=("area", "count"),
            avg_activity_score=("operational_activity_score", "mean"),
            max_activity_score=("operational_activity_score", "max"),
            avg_drilling=("drilling_score", "mean"),
            avg_frac=("frac_score", "mean"),
            avg_production=("production_score", "mean"),
        )
        .reset_index()
    )

    for col in [
        "avg_activity_score",
        "avg_drilling",
        "avg_frac",
        "avg_production",
    ]:
        summary[col] = summary[col].round(1)

    summary["operator_activity_bucket"] = summary["avg_activity_score"].apply(_bucket)

    return summary.sort_values(
        ["avg_activity_score", "max_activity_score"],
        ascending=[False, False],
    ).reset_index(drop=True)


def activity_summary_by_basin(activity_df):
    if activity_df is None or activity_df.empty:
        return pd.DataFrame()

    df = calculate_operational_activity_score(activity_df)

    if "basin" not in df.columns:
        return pd.DataFrame()

    summary = (
        df.groupby("basin", dropna=False)
        .agg(
            areas=("area", "count"),
            avg_activity_score=("operational_activity_score", "mean"),
            max_activity_score=("operational_activity_score", "max"),
            avg_drilling=("drilling_score", "mean"),
            avg_frac=("frac_score", "mean"),
            avg_production=("production_score", "mean"),
        )
        .reset_index()
    )

    for col in [
        "avg_activity_score",
        "avg_drilling",
        "avg_frac",
        "avg_production",
    ]:
        summary[col] = summary[col].round(1)

    return summary.sort_values(
        ["avg_activity_score", "max_activity_score"],
        ascending=[False, False],
    ).reset_index(drop=True)


def top_operational_activity(activity_df, n=20):
    if activity_df is None or activity_df.empty:
        return pd.DataFrame()

    df = calculate_operational_activity_score(activity_df)

    cols = [
        "area",
        "operator",
        "basin",
        "province",
        "operational_activity_score",
        "activity_bucket",
        "drilling_score",
        "frac_score",
        "production_score",
        "seismic_score",
        "well_status_score",
        "activity_note",
    ]

    cols = [c for c in cols if c in df.columns]
    return df[cols].head(n).reset_index(drop=True)
