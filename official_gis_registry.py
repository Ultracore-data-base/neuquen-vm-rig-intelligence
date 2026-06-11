import pandas as pd


def gis_source_status(gis_registry):
    if gis_registry is None or gis_registry.empty:
        return pd.DataFrame()

    df = gis_registry.copy()

    for col in ["province", "status", "priority", "source_type", "layer_name"]:
        if col not in df.columns:
            df[col] = ""

    summary = (
        df.groupby(["province", "status"], dropna=False)
        .agg(
            layers=("layer_name", "count"),
            critical=("priority", lambda x: sum(str(v).lower() == "critical" for v in x)),
            high=("priority", lambda x: sum(str(v).lower() == "high" for v in x)),
            source_types=("source_type", lambda x: ", ".join(sorted(set(str(v) for v in x if str(v)))))
        )
        .reset_index()
        .rename(columns={
            "province": "Province",
            "status": "Status",
            "layers": "Layers",
            "critical": "Critical",
            "high": "High",
            "source_types": "Source Types",
        })
    )

    return summary.sort_values(["Critical", "High", "Layers"], ascending=[False, False, False])


def active_wms_layers_for_province(gis_registry, province):
    if gis_registry is None or gis_registry.empty:
        return []

    df = gis_registry.copy()
    if "province" not in df.columns or "source_type" not in df.columns:
        return []

    mask = (
        df["province"].astype(str).str.lower().eq(str(province).lower())
        & df["source_type"].astype(str).str.upper().eq("WMS")
        & df["status"].astype(str).str.lower().isin(["connected", "verified"])
    )

    out = []
    for _, row in df[mask].iterrows():
        out.append({
            "name": row.get("layer_name", ""),
            "technical_layer": row.get("technical_layer", ""),
            "url": row.get("url", ""),
            "show": str(row.get("priority", "")).lower() == "critical",
        })

    return out


def pending_gis_sources(gis_registry):
    if gis_registry is None or gis_registry.empty:
        return pd.DataFrame()

    df = gis_registry.copy()
    if "status" not in df.columns:
        return pd.DataFrame()

    return df[df["status"].astype(str).str.contains("pending|registry_only|validation", case=False, na=False)].reset_index(drop=True)
