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


def numeric_col(df: pd.DataFrame, col: str, default: float = 0) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(default)
    return pd.Series([default] * len(df))


st.title("Ultracore Energy Intelligence Platform")
st.caption("Argentina-first, LATAM-ready upstream intelligence platform for rigs, workover, frac, e-frac, venting, HVAC, lighting towers and oilfield services.")

# Data
operator_forecast = load_csv("operator_forecast.csv")
operator_signals = load_csv("operator_signals.csv")
operator_area_forecast = load_csv("operator_area_forecast.csv")
permits_pipeline = load_csv("permits_pipeline_auto.csv")
changes_log = load_csv("changes_log.csv")

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


tabs = st.tabs([
    "Executive Summary",
    "Argentina Map",
    "Operator Ranking",
    "Area Ranking",
    "Permit Pipeline",
    "Rig Coverage",
    "Services",
    "Master Data",
    "Score Definitions",
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

    if not operator_forecast.empty:
        st.subheader("Top Operator Rig Demand Ranking")
        st.dataframe(operator_forecast, use_container_width=True)

        if px is not None and "rig_demand_score" in operator_forecast.columns and "operator" in operator_forecast.columns:
            df = operator_forecast.copy()
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
    st.header("Argentina Opportunity Map")

    if not areas.empty and {"lat", "lon"}.issubset(areas.columns):
        df_map = areas.copy()
        df_map["lat"] = pd.to_numeric(df_map["lat"], errors="coerce")
        df_map["lon"] = pd.to_numeric(df_map["lon"], errors="coerce")
        df_map["confidence"] = numeric_col(df_map, "confidence", 40)
        df_map = df_map.dropna(subset=["lat", "lon"])

        if px is not None and not df_map.empty:
            fig = px.scatter_mapbox(
                df_map,
                lat="lat",
                lon="lon",
                color="basin" if "basin" in df_map.columns else None,
                size="confidence",
                hover_data=[
                    c for c in [
                        "area",
                        "operator",
                        "province",
                        "basin",
                        "hydrocarbon",
                        "development_status",
                        "source_note",
                    ] if c in df_map.columns
                ],
                zoom=3.5,
                height=760,
                mapbox_style="open-street-map",
                title="Argentina upstream opportunity map",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Plotly is not available or area_master.csv has no valid coordinates.")
    else:
        st.warning("area_master.csv must include lat and lon fields.")


with tabs[2]:
    st.header("Operator Intelligence")

    if not operator_forecast.empty:
        st.dataframe(operator_forecast, use_container_width=True)
    else:
        st.info("No operator_forecast.csv found yet.")

    if not operator_signals.empty:
        st.subheader("Underlying Operator Signals")
        st.dataframe(operator_signals, use_container_width=True)


with tabs[3]:
    st.header("Area Intelligence")

    if not operator_area_forecast.empty:
        st.dataframe(operator_area_forecast, use_container_width=True)

        if px is not None and {"lat", "lon"}.issubset(operator_area_forecast.columns):
            df = operator_area_forecast.copy()
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
                    height=700,
                    mapbox_style="open-street-map",
                    title="Rig Demand Signals by Area",
                )
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("operator_area_forecast.csv not found yet.")


with tabs[4]:
    st.header("Permit Pipeline")

    if not permits_pipeline.empty:
        st.dataframe(permits_pipeline, use_container_width=True)
    else:
        st.info("permits_pipeline_auto.csv not found yet.")

    if not changes_log.empty:
        st.subheader("Changes Log")
        st.dataframe(changes_log, use_container_width=True)


with tabs[5]:
    st.header("Rig Coverage / Operator Rig Strategy")

    st.markdown("""
    This layer tracks whether demand is already covered by owned rigs, leased rigs or third-party operated contracts.
    It is critical for estimating **Open Rig Opportunity Score**.
    """)

    if not rig_strategy.empty:
        st.dataframe(rig_strategy, use_container_width=True)
    else:
        st.info("operator_rig_strategy.csv not found.")

    if not providers.empty:
        st.subheader("Rig and Service Providers")
        st.dataframe(providers, use_container_width=True)


with tabs[6]:
    st.header("Multi-Service Opportunity Layer")

    st.markdown("""
    Ultracore opportunities are not limited to drilling rigs. The platform also tracks future demand for:
    workover, frac, e-frac, venting solutions, HVAC, lighting towers, power generation, water management,
    facilities, midstream and field support services.
    """)

    if not services.empty:
        st.subheader("Service Master")
        st.dataframe(services, use_container_width=True)

    if not service_rules.empty:
        st.subheader("Service Opportunity Rules")
        st.dataframe(service_rules, use_container_width=True)


with tabs[7]:
    st.header("Master Data")

    mtabs = st.tabs([
        "Countries",
        "Basins",
        "Provinces",
        "Operators",
        "Areas",
        "Sources",
    ])

    with mtabs[0]:
        st.dataframe(countries, use_container_width=True)
    with mtabs[1]:
        st.dataframe(basins, use_container_width=True)
    with mtabs[2]:
        st.dataframe(provinces, use_container_width=True)
    with mtabs[3]:
        st.dataframe(operators, use_container_width=True)
    with mtabs[4]:
        st.dataframe(areas, use_container_width=True)
    with mtabs[5]:
        st.dataframe(sources, use_container_width=True)


with tabs[8]:
    st.header("Score Definitions")

    st.markdown("""
    ### Rig Demand Score
    Probability that an operator will require drilling rigs and associated services in the next 6–18 months.

    - **40% Permits / EIA evidence:** drilling permits, environmental impact studies, PADs, public hearings, official notices.
    - **30% Investor / CAPEX evidence:** investor presentations, strategic plans, production growth guidance, announced investment.
    - **20% Activity intensity:** number and quality of relevant signals, wells/PAD references, active development density.
    - **10% Operator tier / strategic relevance:** major operators and core areas receive higher weight.

    ### Rig Coverage Score
    Measures whether the operator's demand appears already covered by owned rigs, leased rigs or third-party contractors.

    ### Open Rig Opportunity Score
    Demand not yet covered by known rig capacity.

    ### Multi-Service Score
    Extends the opportunity model beyond rigs into workover, frac, e-frac, venting, HVAC, lighting, power, water and facilities.
    """)

    if not score_definitions.empty:
        st.dataframe(score_definitions, use_container_width=True)


with tabs[9]:
    st.header("Data Export")

    export_items = {
        "operator_forecast.csv": operator_forecast,
        "operator_signals.csv": operator_signals,
        "operator_area_forecast.csv": operator_area_forecast,
        "permits_pipeline_auto.csv": permits_pipeline,
        "countries.csv": countries,
        "basin_master.csv": basins,
        "province_master.csv": provinces,
        "operator_master.csv": operators,
        "area_master.csv": areas,
        "service_master.csv": services,
        "rig_provider_master.csv": providers,
        "operator_rig_strategy.csv": rig_strategy,
        "score_definitions.csv": score_definitions,
    }

    for filename, df in export_items.items():
        if not df.empty:
            st.download_button(
                label=f"Download {filename}",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name=filename,
                mime="text/csv",
            )
