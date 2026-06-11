import pandas as pd


def source_summary_by_module(source_registry):
    if source_registry is None or source_registry.empty:
        return pd.DataFrame()

    df = source_registry.copy()

    for col in ["app_module", "source_id", "priority", "status", "category"]:
        if col not in df.columns:
            df[col] = ""

    summary = (
        df.groupby("app_module", dropna=False)
        .agg(
            Sources=("source_id", "count"),
            Critical=("priority", lambda x: sum(str(v).lower() == "critical" for v in x)),
            High=("priority", lambda x: sum(str(v).lower() == "high" for v in x)),
            Categories=("category", lambda x: ", ".join(sorted(set(str(v) for v in x if str(v)))))
        )
        .reset_index()
        .rename(columns={"app_module": "Module"})
    )

    return summary.sort_values(["Critical", "High", "Sources"], ascending=[False, False, False])


def filter_sources(source_registry, category=None, province=None, priority=None):
    if source_registry is None or source_registry.empty:
        return pd.DataFrame()

    df = source_registry.copy()

    if category and "category" in df.columns:
        df = df[df["category"].astype(str).str.lower() == str(category).lower()]

    if province and "province" in df.columns:
        df = df[df["province"].astype(str).str.lower().str.contains(str(province).lower(), na=False)]

    if priority and "priority" in df.columns:
        df = df[df["priority"].astype(str).str.lower() == str(priority).lower()]

    return df.reset_index(drop=True)
