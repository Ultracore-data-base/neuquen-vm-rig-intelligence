from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import plotly.express as px
except Exception:
    px = None


st.set_page_config(
    page_title="Ultracore Energy Intelligence Platform",
    page_icon="🛢️",
    layout="wide",
)

DATA_DIR = Path("data")


def load_csv(filename: str) -> pd.DataFrame:
    path = DATA_DIR / filename
    if path.exists():
        return pd.read_csv(path)
    fallback = Path(filename)
    if fallback.exists():
        return pd.read_csv(fallback)
    return pd.DataFrame()


def clean_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    cols_to_drop = [
        "score_definition",
        "source_note",
    ]
    return df.drop(columns=[c for c in cols_to_drop if c in df.columns], errors="ignore")


def numeric_col(df: pd.DataFrame, col: str, default: float = 0) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(default)
    return pd.Series([default] * len(df))


def show_score_composition():
    st.markdown("### Score Composition")
    st.markdown("""
| Component | Weight |
|---|---:|
| Permits / EIA | 40% |
| Investor / CAPEX Signal | 30% |
| Activity Intensity | 20% |
| Operator Tier / Core Relevance | 10% |
""")


def show_map_notice():
    st.info(
        "Current map uses seeded centroids. For true immersive block-level analysis, "
        "the next step is loading official concession polygons as GeoJSON: "
        "data/area_blocks.geojson. Then the map will display adjudicated area boundaries, "
        "operators, roads, towns and logistics references."
    )


# Load generated intelligence
operator_forecast = load_csv("operator_forecast.csv")
operator_signals = load_csv("operator_signals.csv")
operator_area_forecast = load_csv("operator_area_forecast.csv")
permits_pipeline = load_csv("permits_pipeline_auto.csv")
changes_log = load_csv("changes_log.csv")

# Load master data
countries = load_csv("countries.csv")
basins = load_csv("basin_master.csv")
provinces = load_csv("province_master.csv")
operators = load_csv("operator_master.csv")
areas = load_csv("area_master.csv")
services = load_csv("service_master.csv")
providers = load_csv("rig_provider_master.csv")
score_definitions = load_csv("score_definitions.csv")
rig_strategy = load_csv("operator_rig_strategy.csv")
service_rules = load_csv("service_opportunity_rules.csv")
sources = load_csv("source_registry.csv")


st.title("Ultracore Energy Intelligence Platform")
st.caption(
    "Argentina-first, LATAM-ready upstream intelligence platform for rigs, workover, "
    "frac, e-frac, venting, HVAC, lighting towers and oilfield services."
)

tabs = st.tabs([
    "Executive Summary",
    "Immersive Map",
    "Operator Intelligence",
    "Area Intelligence",
    "Permit Pipeline",
    "Rig Coverage",
    "Multi-Service",
    "Master Data",
    "Data Export",
])


with tabs[0]:
    st.header("Executive Summary")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Countries", len(countries))
    c2.metric("Basins", len(basins))
    c3.metric("Areas / blocks", len(areas))
    c4.metric("Operators", len(operators))

    st.markdown("""
**Platform objective:** identify future commercial opportunities for Ultracore by crossing regulatory signals,
EIA permits, investor plans, media/LinkedIn intelligence, rig contracts, provider coverage and service demand.

**Core questions:**
- Which operator will need capacity?
- In which basin and area?
- Which service will be required?
- Who is the incumbent provider?
- Is the demand already covered or open?
""")

    show_score_composition()

    if not operator_forecast.empty:
        st.subheader("Top Operator Rig Demand Ranking")
        clean_forecast = clean_table(operator_forecast)
        st.dataframe(clean_forecast, use_container_width=True)

        if px is not None and "rig_demand_score" in operator_forecast.columns and "operator" in operator_forecast.columns:
            df = clean_forecast.copy()
            df["rig_demand_score"] = numeric_col(df, "rig_demand_score")
            fig = px.bar(
                df.sort_values("rig_demand_score", ascending=True),
                x="rig_demand_score",
                y="operator",
                orientation="h",
                title="Rig Demand Score by Operator",
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("operator_forecast.csv not found yet. Run the investor workflow.")


with tabs[1]:
    st.header("Immersive Argentina Opportunity Map")
    show_map_notice()

    st.markdown("""
**Target map behavior:**
- National Argentina view.
- Zoom into basin.
- Zoom into province.
- Select adjudicated area / concession.
- Show operator, permits, EIA, rig demand, provider coverage and logistics references.
- Future upgrade: official concession polygons instead of centroid points.
""")

    if not areas.empty and {"lat", "lon"}.issubset(areas.columns):
        df_map = areas.copy()
        df_map["lat"] = pd.to_numeric(df_map["lat"], errors="coerce")
        df_map["lon"] = pd.to_numeric(df_map["lon"], errors="coerce")
        df_map["confidence"] = numeric_col(df_map, "confidence", 40)
        df_map = df_map.dropna(subset=["lat", "lon"])

        if px is not None and not df_map.empty:
            hover_cols = [
                c for c in [
                    "area",
                    "operator",
                    "province",
                    "basin",
                    "hydrocarbon",
                    "development_status",
                ] if c in df_map.columns
            ]

            fig = px.scatter_mapbox(
                df_map,
                lat="lat",
                lon="lon",
                color="basin" if "basin" in df_map.columns else None,
                size="confidence",
                hover_data=hover_cols,
                zoom=3.5,
                height=820,
                mapbox_style="open-street-map",
                title="Argentina upstream opportunity map - centroid layer",
            )
            fig.update_layout(
                margin={"r": 0, "t": 45, "l": 0, "b": 0},
                legend_title_text="Basin",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Plotly is not available or area_master.csv has no valid coordinates.")
    else:
        st.warning("area_master.csv must include lat and lon fields.")

    st.subheader("Area Master Reference")
    st.dataframe(clean_table(areas), use_container_width=True)


with tabs[2]:
    st.header("Operator Intelligence")
    show_score_composition()

    if not operator_forecast.empty:
        clean_forecast = clean_table(operator_forecast)
        st.dataframe(clean_forecast, use_container_width=True)

        if px is not None and "rig_demand_score" in clean_forecast.columns and "operator" in clean_forecast.columns:
            df = clean_forecast.copy()
            df["rig_demand_score"] = numeric_col(df, "rig_demand_score")
            fig = px.bar(
                df.sort_values("rig_demand_score", ascending=True),
                x="rig_demand_score",
                y="operator",
                orientation="h",
                title="Operator Rig Demand Score",
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No operator_forecast.csv found yet.")

    if not operator_signals.empty:
        st.subheader("Underlying Operator Signals")
        st.dataframe(clean_table(operator_signals), use_container_width=True)


with tabs[3]:
    st.header("Area Intelligence")

    if not operator_area_forecast.empty:
        clean_area = clean_table(operator_area_forecast)
        st.dataframe(clean_area, use_container_width=True)

        if px is not None and {"lat", "lon"}.issubset(clean_area.columns):
            df = clean_area.copy()
            df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
            df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

            if "rig_demand_score" in df.columns:
                df["rig_demand_score"] = numeric_col(df, "rig_demand_score")

            df = df.dropna(subset=["lat", "lon"])

            if not df.empty:
                fig = px.scatter_mapbox(
                    df,
                    lat="lat",
                    lon="lon",
                    color="operator" if "operator" in df.columns else None,
                    size="rig_demand_score" if "rig_demand_score" in df.columns else None,
                    hover_data=[c for c in ["area", "operator", "signals", "rig_demand_score"] if c in df.columns],
                    zoom=5.8,
                    height=760,
                    mapbox_style="open-street-map",
                    title="Rig Demand Signals by Area",
                )
                fig.update_layout(margin={"r": 0, "t": 45, "l": 0, "b": 0})
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("operator_area_forecast.csv not found yet.")


with tabs[4]:
    st.header("Permit Pipeline")

    if not permits_pipeline.empty:
        st.dataframe(clean_table(permits_pipeline), use_container_width=True)
    else:
        st.info("permits_pipeline_auto.csv not found yet.")

    if not changes_log.empty:
        st.subheader("Changes Log")
        st.dataframe(clean_table(changes_log), use_container_width=True)


with tabs[5]:
    st.header("Rig Coverage / Operator Rig Strategy")

    st.markdown("""
This layer tracks whether demand is already covered by owned rigs, leased rigs or third-party operated contracts.
It is critical for estimating **Open Rig Opportunity Score**.
""")

    if not rig_strategy.empty:
        st.dataframe(clean_table(rig_strategy), use_container_width=True)
    else:
        st.info("operator_rig_strategy.csv not found.")

    if not providers.empty:
        st.subheader("Rig and Service Providers")
        st.dataframe(clean_table(providers), use_container_width=True)


with tabs[6]:
    st.header("Multi-Service Opportunity Layer")

    st.markdown("""
Ultracore opportunities are not limited to drilling rigs. The platform also tracks future demand for:

- Workover
- Frac
- E-Frac
- Venting solutions
- HVAC
- Lighting towers
- Power generation
- Water management
- Facilities
- Midstream
""")

    if not services.empty:
        st.subheader("Service Master")
        st.dataframe(clean_table(services), use_container_width=True)

    if not service_rules.empty:
        st.subheader("Service Opportunity Rules")
        st.dataframe(clean_table(service_rules), use_container_width=True)


with tabs[7]:
    st.header("Master Data")

    mtabs = st.tabs([
        "Countries",
        "Basins",
        "Provinces",
        "Operators",
        "Areas",
        "Sources",
        "Score Definitions",
    ])

    with mtabs[0]:
        st.dataframe(clean_table(countries), use_container_width=True)
    with mtabs[1]:
        st.dataframe(clean_table(basins), use_container_width=True)
    with mtabs[2]:
        st.dataframe(clean_table(provinces), use_container_width=True)
    with mtabs[3]:
        st.dataframe(clean_table(operators), use_container_width=True)
    with mtabs[4]:
        st.dataframe(clean_table(areas), use_container_width=True)
    with mtabs[5]:
        st.dataframe(clean_table(sources), use_container_width=True)
    with mtabs[6]:
        st.dataframe(clean_table(score_definitions), use_container_width=True)


with tabs[8]:
    st.header("Data Export")

    export_items = {
        "operator_forecast.csv": clean_table(operator_forecast),
        "operator_signals.csv": clean_table(operator_signals),
        "operator_area_forecast.csv": clean_table(operator_area_forecast),
        "permits_pipeline_auto.csv": clean_table(permits_pipeline),
        "countries.csv": clean_table(countries),
        "basin_master.csv": clean_table(basins),
        "province_master.csv": clean_table(provinces),
        "operator_master.csv": clean_table(operators),
        "area_master.csv": clean_table(areas),
        "service_master.csv": clean_table(services),
        "rig_provider_master.csv": clean_table(providers),
        "operator_rig_strategy.csv": clean_table(rig_strategy),
        "score_definitions.csv": clean_table(score_definitions),
    }

    for filename, df in export_items.items():
        if not df.empty:
            st.download_button(
                label=f"Download {filename}",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name=filename,
                mime="text/csv",
            )
