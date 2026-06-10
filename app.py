from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import folium
    from folium.plugins import Fullscreen, MiniMap, MeasureControl
    from streamlit_folium import st_folium
except Exception:
    folium = None
    st_folium = None

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


def load_csv(filename):
    path = DATA_DIR / filename
    if path.exists():
        return pd.read_csv(path)
    fallback = Path(filename)
    if fallback.exists():
        return pd.read_csv(fallback)
    return pd.DataFrame()


def clean_table(df):
    if df.empty:
        return df
    hidden_cols = ["score_definition"]
    return df.drop(columns=[c for c in hidden_cols if c in df.columns])


def to_num(df, col, default=0):
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(default)
    return pd.Series([default] * len(df))


# Load data
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


st.title("Ultracore Energy Intelligence Platform")
st.caption(
    "Argentina-first, LATAM-ready upstream intelligence platform for rigs, workover, frac, e-frac, venting, HVAC, lighting towers and oilfield services."
)

tabs = st.tabs([
    "Executive Summary",
    "Immersive GIS Map",
    "Operator Intelligence",
    "Area Intelligence",
    "Permit Pipeline",
    "Rig Coverage",
    "Multi-Service",
    "Master Data",
    "Score",
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
    EIA permits, investor plans, media/LinkedIn intelligence, rig contracts, provider coverage and multi-service demand.

    **Core question:** what operator, in what basin and area, will need which service, when, and who is the incumbent provider?
    """)

    if not operator_forecast.empty:
        df = clean_table(operator_forecast)
        st.subheader("Top Operator Rig Demand Ranking")
        st.dataframe(df, use_container_width=True)

        if px is not None and {"operator", "rig_demand_score"}.issubset(df.columns):
            chart_df = df.copy()
            chart_df["rig_demand_score"] = to_num(chart_df, "rig_demand_score")
            fig = px.bar(
                chart_df.sort_values("rig_demand_score", ascending=True),
                x="rig_demand_score",
                y="operator",
                orientation="h",
                title="Rig Demand Score by Operator",
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("operator_forecast.csv not found yet. Run the investor workflow.")


with tabs[1]:
    st.header("Immersive GIS Map")

    st.markdown("""
    This map is designed as the operational/geographic layer of UEIP. It supports zoom, pan, base-map switching,
    satellite view, measurement tools and official WMS layers where available.
    """)

    if folium is None or st_folium is None:
        st.error("folium or streamlit-folium is not installed. Check requirements.txt.")
    else:
        m = folium.Map(
            location=[-38.5, -68.8],
            zoom_start=5,
            tiles=None,
            control_scale=True,
        )

        folium.TileLayer(
            "OpenStreetMap",
            name="OpenStreetMap / roads",
            control=True,
        ).add_to(m)

        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            name="Satellite / Esri World Imagery",
            control=True,
        ).add_to(m)

        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            name="Topographic / Esri",
            control=True,
        ).add_to(m)

        # Neuquen official WMS base endpoint.
        # Layer names may need adjustment if the GeoServer published names differ.
        neuquen_wms = "https://hidrocarburos.energianeuquen.gob.ar/geoserver/wms"

        wms_layers = [
            ("Hidrocarburos:Areas", "Neuquen - Areas / concessions"),
            ("Hidrocarburos:Pozos_VM", "Neuquen - Vaca Muerta wells"),
            ("Hidrocarburos:Pozos", "Neuquen - Wells"),
            ("Hidrocarburos:Ductos", "Neuquen - Ducts"),
            ("Hidrocarburos:Instalaciones", "Neuquen - Facilities"),
            ("Hidrocarburos:Locaciones", "Neuquen - Locations"),
        ]

        for layer_name, display_name in wms_layers:
            try:
                folium.raster_layers.WmsTileLayer(
                    url=neuquen_wms,
                    layers=layer_name,
                    name=display_name,
                    fmt="image/png",
                    transparent=True,
                    version="1.1.1",
                    overlay=True,
                    control=True,
                    show=False,
                ).add_to(m)
            except Exception:
                pass

        if not areas.empty and {"lat", "lon"}.issubset(areas.columns):
            df_map = areas.copy()
            df_map["lat"] = pd.to_numeric(df_map["lat"], errors="coerce")
            df_map["lon"] = pd.to_numeric(df_map["lon"], errors="coerce")
            df_map = df_map.dropna(subset=["lat", "lon"])

            fg = folium.FeatureGroup(name="UEIP seeded areas / centroids", show=True)

            for _, row in df_map.iterrows():
                popup_html = f"""
                <b>Area:</b> {row.get('area', '')}<br>
                <b>Operator:</b> {row.get('operator', '')}<br>
                <b>Basin:</b> {row.get('basin', '')}<br>
                <b>Province:</b> {row.get('province', '')}<br>
                <b>Hydrocarbon:</b> {row.get('hydrocarbon', '')}<br>
                <b>Status:</b> {row.get('development_status', '')}<br>
                <b>Source note:</b> {row.get('source_note', '')}
                """
                folium.CircleMarker(
                    location=[row["lat"], row["lon"]],
                    radius=7,
                    popup=folium.Popup(popup_html, max_width=400),
                    tooltip=f"{row.get('area', '')} - {row.get('operator', '')}",
                    fill=True,
                    fill_opacity=0.75,
                ).add_to(fg)

            fg.add_to(m)

        Fullscreen(position="topright").add_to(m)
        MiniMap(toggle_display=True).add_to(m)
        MeasureControl(position="topleft").add_to(m)
        folium.LayerControl(collapsed=False).add_to(m)

        st_folium(m, width=None, height=820)


with tabs[2]:
    st.header("Operator Intelligence")

    if not operator_forecast.empty:
        st.dataframe(clean_table(operator_forecast), use_container_width=True)
    else:
        st.info("operator_forecast.csv not found yet.")

    if not operator_signals.empty:
        st.subheader("Underlying Signals")
        st.dataframe(clean_table(operator_signals), use_container_width=True)


with tabs[3]:
    st.header("Area Intelligence")

    if not operator_area_forecast.empty:
        st.dataframe(clean_table(operator_area_forecast), use_container_width=True)
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

    if not providers.empty:
        st.subheader("Rig and Service Providers")
        st.dataframe(clean_table(providers), use_container_width=True)


with tabs[6]:
    st.header("Multi-Service Opportunity Layer")

    st.markdown("""
    Ultracore opportunities are not limited to drilling rigs.

    Services tracked:
    - Drilling rigs
    - Workover
    - Frac
    - E-Frac
    - Venting / gas recovery
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

    mtabs = st.tabs(["Countries", "Basins", "Provinces", "Operators", "Areas", "Sources"])

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


with tabs[8]:
    st.header("Score Composition")

    st.markdown("""
    ### Rig Demand Score

    | Score Component | Weight |
    |---|---:|
    | Permits / EIA | 40% |
    | Investor / CAPEX Signal | 30% |
    | Activity Intensity | 20% |
    | Operator Tier / Core Relevance | 10% |

    The score estimates the probability that an operator will require drilling rigs or associated services within the next 6–18 months.

    ### Rig Coverage Score

    Measures whether the operator's demand appears already covered by owned rigs, leased rigs or third-party contractors.

    ### Open Rig Opportunity Score

    Demand not yet covered by known rig capacity.

    ### Multi-Service Score

    Extends the opportunity model beyond rigs into workover, frac, e-frac, venting, HVAC, lighting, power, water and facilities.
    """)


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
                data=clean_table(df).to_csv(index=False).encode("utf-8"),
                file_name=filename,
                mime="text/csv",
            )
