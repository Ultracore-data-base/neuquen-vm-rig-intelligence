import pandas as pd


def dataset_status_summary(dataset_registry):
    if dataset_registry is None or dataset_registry.empty:
        return pd.DataFrame()

    df = dataset_registry.copy()

    for col in ["category", "priority", "status", "dataset_id", "rig_score_weight"]:
        if col not in df.columns:
            df[col] = ""

    df["rig_score_weight"] = pd.to_numeric(df["rig_score_weight"], errors="coerce").fillna(0)

    summary = (
        df.groupby(["category", "status"], dropna=False)
        .agg(
            datasets=("dataset_id", "count"),
            critical=("priority", lambda x: sum(str(v).lower() == "critical" for v in x)),
            high=("priority", lambda x: sum(str(v).lower() == "high" for v in x)),
            score_weight=("rig_score_weight", "sum")
        )
        .reset_index()
        .rename(columns={
            "category": "Category",
            "status": "Status",
            "datasets": "Datasets",
            "critical": "Critical",
            "high": "High",
            "score_weight": "Rig Score Weight"
        })
    )

    return summary.sort_values(["Critical", "High", "Rig Score Weight"], ascending=[False, False, False])


def rig_score_weight_table(dataset_registry):
    if dataset_registry is None or dataset_registry.empty:
        return pd.DataFrame()

    df = dataset_registry.copy()

    if "rig_score_weight" not in df.columns:
        return pd.DataFrame()

    df["rig_score_weight"] = pd.to_numeric(df["rig_score_weight"], errors="coerce").fillna(0)

    out = df[df["rig_score_weight"] > 0][[
        "dataset_id",
        "dataset_name",
        "category",
        "business_use",
        "rig_score_weight",
        "status",
        "priority"
    ]].copy()

    return out.sort_values("rig_score_weight", ascending=False).reset_index(drop=True)


def critical_dataset_backlog(dataset_registry):
    if dataset_registry is None or dataset_registry.empty:
        return pd.DataFrame()

    df = dataset_registry.copy()

    if "priority" not in df.columns:
        return pd.DataFrame()

    mask = df["priority"].astype(str).str.lower().isin(["critical", "high"])
    return df[mask].sort_values(["priority", "category", "dataset_id"]).reset_index(drop=True)
