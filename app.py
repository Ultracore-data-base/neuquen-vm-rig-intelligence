# Paste this into app.py after the current investor / permit tabs section, or use it to replace the old investor snippet.
from pathlib import Path
import pandas as pd
import streamlit as st

try:
    import plotly.express as px
except Exception:
    px = None

st.header('Rig Demand Intelligence')
st.markdown('''
**Rig Demand Score definition**  
Score from 0 to 100 estimating the probability that an operator will require drilling rigs and associated services in the next 6–18 months.

- **40% Permits / EIA evidence:** recent drilling permits, environmental impact studies, PADs, public hearings, official notices.
- **30% Investor / CAPEX evidence:** investor presentations, strategic plans, production growth guidance, announced investment.
- **20% Activity intensity:** number and quality of relevant signals, wells/PAD references, Vaca Muerta references.
- **10% Operator tier / core-area relevance:** major operators and signals in core Vaca Muerta areas receive higher weight.
''')

forecast_path = Path('data/operator_forecast.csv')
signals_path = Path('data/operator_signals.csv')
area_path = Path('data/operator_area_forecast.csv')

if forecast_path.exists():
    forecast = pd.read_csv(forecast_path)
    st.subheader('Operator Rig Demand Ranking')
    st.dataframe(forecast, use_container_width=True)
    if not forecast.empty and px is not None:
        fig = px.bar(forecast.sort_values('rig_demand_score', ascending=True), x='rig_demand_score', y='operator', orientation='h', title='Rig Demand Score by Operator')
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info('operator_forecast.csv not found yet. Run the investor workflow once.')

if area_path.exists():
    by_area = pd.read_csv(area_path)
    st.subheader('Geographic Opportunity Map by Area')
    st.caption('Map points are area-level centroids. They reflect where permits/EIA/investor signals concentrate, not exact well coordinates.')
    map_df = by_area.dropna(subset=['lat','lon']) if {'lat','lon'}.issubset(by_area.columns) else pd.DataFrame()
    if not map_df.empty and px is not None:
        fig = px.scatter_mapbox(
            map_df,
            lat='lat', lon='lon',
            size='rig_demand_score', color='operator',
            hover_name='area',
            hover_data=['operator','signals','rig_demand_score'],
            zoom=6, height=620,
            title='Rig Demand Signals by Area'
        )
        fig.update_layout(mapbox_style='open-street-map', margin={'r':0,'t':40,'l':0,'b':0})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning('No area-level coordinates available yet. Signals will appear here once area names match the AREA_COORDS registry.')
    st.dataframe(by_area, use_container_width=True)
else:
    st.info('operator_area_forecast.csv not found yet. Run the investor workflow once.')

if signals_path.exists():
    signals = pd.read_csv(signals_path)
    st.subheader('Underlying Signals')
    st.dataframe(signals, use_container_width=True)

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
