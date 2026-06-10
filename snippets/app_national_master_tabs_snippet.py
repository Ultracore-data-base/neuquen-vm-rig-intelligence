
# === UEIP NATIONAL MASTER DATA TAB SNIPPET ===
# Paste this into app.py after loading Streamlit imports and tabs.
# Requires: pandas as pd, plotly.express as px, pathlib.Path

from pathlib import Path
UEIP_DATA_DIR = Path("data")

def load_master_csv(name):
    path = UEIP_DATA_DIR / name
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()

countries = load_master_csv("countries.csv")
basins = load_master_csv("basin_master.csv")
areas = load_master_csv("area_master.csv")
operators = load_master_csv("operator_master.csv")
services = load_master_csv("service_master.csv")
providers = load_master_csv("rig_provider_master.csv")
scores = load_master_csv("score_definitions.csv")
rig_strategy = load_master_csv("operator_rig_strategy.csv")

st.header("Ultracore Energy Intelligence Platform - National Master Data")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Countries", len(countries))
m2.metric("Basins", len(basins))
m3.metric("Areas / blocks seeded", len(areas))
m4.metric("Operators", len(operators))

master_tabs = st.tabs(["National map", "Basins", "Operators", "Services", "Rig coverage", "Score definitions"])

with master_tabs[0]:
    st.subheader("Argentina master opportunity map")
    if not areas.empty and {"lat","lon"}.issubset(areas.columns):
        df_map = areas.copy()
        df_map["lat"] = pd.to_numeric(df_map["lat"], errors="coerce")
        df_map["lon"] = pd.to_numeric(df_map["lon"], errors="coerce")
        df_map["confidence"] = pd.to_numeric(df_map["confidence"], errors="coerce").fillna(40)
        df_map = df_map.dropna(subset=["lat","lon"])
        fig = px.scatter_mapbox(
            df_map,
            lat="lat",
            lon="lon",
            color="basin",
            size="confidence",
            hover_data=["area","operator","province","basin","hydrocarbon","development_status","source_note"],
            zoom=3.6,
            height=760,
            mapbox_style="open-street-map",
            title="Argentina upstream opportunity map - seed layer"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("area_master.csv must include lat/lon fields.")

with master_tabs[1]:
    st.dataframe(basins, use_container_width=True)

with master_tabs[2]:
    st.dataframe(operators, use_container_width=True)

with master_tabs[3]:
    st.dataframe(services, use_container_width=True)

with master_tabs[4]:
    st.subheader("Operator rig strategy / coverage seed")
    st.dataframe(rig_strategy, use_container_width=True)

with master_tabs[5]:
    st.subheader("Score definitions")
    st.dataframe(scores, use_container_width=True)
