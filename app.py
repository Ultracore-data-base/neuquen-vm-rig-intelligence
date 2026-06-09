
import streamlit as st
import pandas as pd
import requests
from io import StringIO
from datetime import datetime
import plotly.express as px

st.set_page_config(page_title="Vaca Muerta Rig Intelligence", layout="wide")

WFS_BASE = "https://hidrocarburos.energianeuquen.gob.ar/geoserver/Hidrocarburos/wfs"
LAYER_POZOS_VM = "Hidrocarburos:Pozos_VM"

@st.cache_data(ttl=24*60*60, show_spinner=True)
def load_wfs_csv(layer, max_features=0):
    params = {
        "service": "WFS",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeName": layer,
        "outputFormat": "csv",
    }
    if max_features and int(max_features) > 0:
        params["maxFeatures"] = int(max_features)
    r = requests.get(WFS_BASE, params=params, timeout=120)
    r.raise_for_status()
    return pd.read_csv(StringIO(r.text))

def normalize(df):
    df = df.copy()
    df.columns = [str(c).strip().upper() for c in df.columns]
    return df

def col(df, options):
    for c in options:
        if c in df.columns:
            return c
    return None

def score_permit(row):
    score = 0
    status = str(row.get("PERMIT_STATUS", "")).lower()
    wells = pd.to_numeric(row.get("PERMITTED_WELLS", 0), errors="coerce")
    wells = 0 if pd.isna(wells) else wells
    days = pd.to_numeric(row.get("DAYS_SINCE_PUBLICATION", 999), errors="coerce")
    days = 999 if pd.isna(days) else days

    if any(x in status for x in ["granted", "published", "license", "approved"]):
        score += 35
    elif any(x in status for x in ["process", "eia", "hearing"]):
        score += 25
    elif "announced" in status:
        score += 15

    if wells >= 20:
        score += 25
    elif wells >= 10:
        score += 20
    elif wells >= 4:
        score += 15
    elif wells >= 1:
        score += 8

    if "(h)" in str(row.get("PAD_OR_WELLS", "")).lower() or "horizontal" in str(row.get("WELL_TYPE", "")).lower():
        score += 15

    if "unconventional" in str(row.get("RESERVOIR", "")).lower() or "vaca" in str(row.get("FORMATION", "")).lower():
        score += 10

    if days <= 90:
        score += 15
    elif days <= 180:
        score += 12
    elif days <= 365:
        score += 7

    return min(int(score), 100)

def priority(score):
    if score >= 80: return "Tier 1 - Immediate follow-up"
    if score >= 60: return "Tier 2 - Qualify / monitor"
    if score >= 40: return "Tier 3 - Early signal"
    return "Low priority"

def prepare_permits(df):
    p = normalize(df)
    if "PUBLICATION_DATE" in p.columns:
        p["PUBLICATION_DATE"] = pd.to_datetime(p["PUBLICATION_DATE"], errors="coerce")
        p["DAYS_SINCE_PUBLICATION"] = (pd.Timestamp.today().normalize() - p["PUBLICATION_DATE"]).dt.days
    else:
        p["DAYS_SINCE_PUBLICATION"] = 999
    for c, v in {"RESERVOIR":"Unconventional", "FORMATION":"Vaca Muerta", "WELL_TYPE":"Horizontal / probable"}.items():
        if c not in p.columns:
            p[c] = v
    p["RIG_OPPORTUNITY_SCORE"] = p.apply(score_permit, axis=1)
    p["COMMERCIAL_PRIORITY"] = p["RIG_OPPORTUNITY_SCORE"].apply(priority)
    return p

st.title("Vaca Muerta / Neuquén Rig Intelligence Dashboard")
st.caption("Official Neuquén GIS wells + forward drilling permit pipeline + Stamper/ARX rig opportunity scoring")

with st.sidebar:
    st.header("Data Sources")
    source = st.radio("VM wells source", ["Live Neuquén WFS", "Upload Pozos_VM CSV"], index=0)
    max_records = st.number_input("Max WFS records; 0 = all", min_value=0, max_value=50000, value=0, step=1000)
    uploaded_wells = None
    if source == "Upload Pozos_VM CSV":
        uploaded_wells = st.file_uploader("Upload Pozos_VM CSV", type=["csv"])
    st.divider()
    st.header("Permit Pipeline")
    permits_file = st.file_uploader("Upload permit / environmental notices CSV", type=["csv"])

try:
    if source == "Live Neuquén WFS":
        wells = load_wfs_csv(LAYER_POZOS_VM, max_records)
    else:
        if uploaded_wells is None:
            st.warning("Upload Pozos_VM CSV to continue.")
            st.stop()
        wells = pd.read_csv(uploaded_wells)
except Exception as e:
    st.error(f"Could not load well data: {e}")
    st.stop()

wells = normalize(wells)

operator_col = col(wells, ["OPERADOR", "OPERATOR"])
area_col = col(wells, ["AREA_LEGAL", "FIELD_NAME", "YACIMIENTO", "AREA"])
state_col = col(wells, ["ESTADO_GIS", "ESTADO", "ORIGINAL_STATUS"])
lat_col = col(wells, ["LATITUD", "LATITUDE"])
lon_col = col(wells, ["LONGITUD", "LONGITUDE"])
year_col = col(wells, ["AÑO_PERF", "ANO_PERF", "YEAR_PERF"])
well_col = col(wells, ["WELL_NAME", "WELL_S_NAME", "UWI_NQN"])

if lat_col and lon_col:
    wells[lat_col] = pd.to_numeric(wells[lat_col], errors="coerce")
    wells[lon_col] = pd.to_numeric(wells[lon_col], errors="coerce")

k1, k2, k3, k4 = st.columns(4)
k1.metric("VM Wells Loaded", f"{len(wells):,}")
k2.metric("Operators", wells[operator_col].nunique() if operator_col else "n/a")
k3.metric("Areas / Fields", wells[area_col].nunique() if area_col else "n/a")
k4.metric("Data Refresh", datetime.now().strftime("%Y-%m-%d %H:%M"))

tabs = st.tabs(["Executive Summary", "Interactive Map", "Operator / Area Ranking", "Permit Pipeline", "Rig Demand Score", "Data Export"])

with tabs[0]:
    st.subheader("Executive Summary")
    if operator_col:
        op_rank = wells.groupby(operator_col).size().reset_index(name="VM_WELLS").sort_values("VM_WELLS", ascending=False)
        st.dataframe(op_rank, use_container_width=True, height=420)
        fig = px.bar(op_rank.head(15), x=operator_col, y="VM_WELLS", title="Top VM operators by well count")
        st.plotly_chart(fig, use_container_width=True)

with tabs[1]:
    st.subheader("Interactive Vaca Muerta Map")
    map_frames = []
    if lat_col and lon_col:
        m = wells.dropna(subset=[lat_col, lon_col]).copy()
        m["MAP_LAYER"] = "Existing VM Wells"
        m["MAP_LAT"] = m[lat_col]
        m["MAP_LON"] = m[lon_col]
        m["MAP_OPERATOR"] = m[operator_col] if operator_col else "Unknown"
        m["MAP_AREA"] = m[area_col] if area_col else "Unknown"
        m["MAP_STATUS"] = m[state_col] if state_col else "Unknown"
        m["MAP_SIZE"] = 5
        map_frames.append(m)

    if permits_file:
        permits = prepare_permits(pd.read_csv(permits_file))
        if "LATITUDE" in permits.columns and "LONGITUDE" in permits.columns:
            permits["LATITUDE"] = pd.to_numeric(permits["LATITUDE"], errors="coerce")
            permits["LONGITUDE"] = pd.to_numeric(permits["LONGITUDE"], errors="coerce")
            pp = permits.dropna(subset=["LATITUDE", "LONGITUDE"]).copy()
            if not pp.empty:
                pp["MAP_LAYER"] = "Forward Permit Pipeline"
                pp["MAP_LAT"] = pp["LATITUDE"]
                pp["MAP_LON"] = pp["LONGITUDE"]
                pp["MAP_OPERATOR"] = pp["OPERATOR"] if "OPERATOR" in pp.columns else "Unknown"
                pp["MAP_AREA"] = pp["AREA"] if "AREA" in pp.columns else "Unknown"
                pp["MAP_STATUS"] = pp["COMMERCIAL_PRIORITY"]
                pp["MAP_SIZE"] = 14
                map_frames.append(pp)

    if map_frames:
        allmap = pd.concat(map_frames, ignore_index=True, sort=False)
        hover_cols = [c for c in ["MAP_LAYER","MAP_OPERATOR","MAP_AREA","MAP_STATUS","RIG_OPPORTUNITY_SCORE",well_col,"PAD_OR_WELLS","PERMITTED_WELLS","PERMIT_STATUS"] if c and c in allmap.columns]
        fig = px.scatter_mapbox(
            allmap,
            lat="MAP_LAT",
            lon="MAP_LON",
            color="MAP_OPERATOR",
            size="MAP_SIZE",
            hover_data=hover_cols,
            zoom=7.5,
            height=760,
            mapbox_style="open-street-map",
            title="Existing VM Wells + Forward Permit Pipeline"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No georeferenced data available.")

with tabs[2]:
    st.subheader("Operator / Area Ranking")
    if operator_col and area_col:
        summary = wells.groupby([operator_col, area_col]).size().reset_index(name="VM_WELLS").sort_values("VM_WELLS", ascending=False)
        st.dataframe(summary, use_container_width=True, height=620)

with tabs[3]:
    st.subheader("Forward-Looking Permit Pipeline")
    if permits_file:
        permits = prepare_permits(pd.read_csv(permits_file))
        st.dataframe(permits.sort_values("RIG_OPPORTUNITY_SCORE", ascending=False), use_container_width=True, height=600)
        fig = px.bar(
            permits.groupby("OPERATOR")["RIG_OPPORTUNITY_SCORE"].max().reset_index().sort_values("RIG_OPPORTUNITY_SCORE", ascending=False),
            x="OPERATOR",
            y="RIG_OPPORTUNITY_SCORE",
            title="Highest rig opportunity score by operator"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Upload the permit/environmental CSV. Use permits_template.csv included in the repository.")

with tabs[4]:
    st.subheader("Rig Demand Score")
    st.markdown("""
    **Score logic**
    - Permit / environmental license status: up to 35 points
    - Number of permitted wells: up to 25 points
    - Horizontal / PAD signal: up to 15 points
    - Unconventional / Vaca Muerta signal: up to 10 points
    - Publication recency: up to 15 points
    """)

with tabs[5]:
    st.subheader("Data Export")
    st.download_button("Download VM wells CSV", wells.to_csv(index=False).encode("utf-8"), "vm_wells_neuquen.csv", "text/csv")
    if permits_file:
        permits = prepare_permits(pd.read_csv(permits_file))
        st.download_button("Download scored permit pipeline CSV", permits.to_csv(index=False).encode("utf-8"), "scored_permit_pipeline.csv", "text/csv")
