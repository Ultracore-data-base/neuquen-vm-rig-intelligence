
import streamlit as st
import pandas as pd
import requests
from io import StringIO
from datetime import datetime
import plotly.express as px

st.set_page_config(page_title="Neuquen / Vaca Muerta Drilling Intelligence", layout="wide")

WFS_BASE = "https://hidrocarburos.energianeuquen.gob.ar/geoserver/Hidrocarburos/wfs"
LAYER_POZOS_VM = "Hidrocarburos:Pozos_VM"

@st.cache_data(ttl=24*60*60, show_spinner=True)
def load_wfs_csv(layer, max_features=None):
    params = {
        "service": "WFS",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeName": layer,
        "outputFormat": "csv",
    }
    if max_features:
        params["maxFeatures"] = max_features
    r = requests.get(WFS_BASE, params=params, timeout=90)
    r.raise_for_status()
    return pd.read_csv(StringIO(r.text))

def norm(df):
    df = df.copy()
    df.columns = [str(c).strip().upper() for c in df.columns]
    return df

def find_col(df, names):
    for n in names:
        if n in df.columns:
            return n
    return None

def score_permit(row):
    score = 0
    status = str(row.get("PERMIT_STATUS", "")).lower()
    wells = pd.to_numeric(row.get("PERMITTED_WELLS", 0), errors="coerce")
    wells = 0 if pd.isna(wells) else wells
    days = pd.to_numeric(row.get("DAYS_SINCE_PUBLICATION", 999), errors="coerce")
    days = 999 if pd.isna(days) else days

    if "granted" in status or "published" in status or "license" in status:
        score += 40
    elif "process" in status or "eia" in status:
        score += 28
    elif "announced" in status:
        score += 15

    if wells >= 10:
        score += 20
    elif wells >= 4:
        score += 14
    elif wells >= 1:
        score += 8

    if "(h)" in str(row.get("PAD_OR_WELLS", "")).lower() or "horizontal" in str(row.get("WELL_TYPE", "")).lower():
        score += 15

    if "unconventional" in str(row.get("RESERVOIR", "")).lower():
        score += 10

    if days <= 180:
        score += 15
    elif days <= 365:
        score += 8

    return min(int(score), 100)

def priority(score):
    if score >= 80:
        return "Tier 1 - Immediate commercial follow-up"
    if score >= 60:
        return "Tier 2 - Monitor / qualify"
    if score >= 40:
        return "Tier 3 - Early intelligence"
    return "Low priority"

st.title("Neuquen / Vaca Muerta Drilling Intelligence")
st.caption("Official Neuquen GIS + environmental permit pipeline + rig opportunity scoring")

with st.sidebar:
    st.header("Data")
    mode = st.radio("VM wells source", ["Live Neuquen WFS", "Upload Pozos_VM CSV"], index=0)
    upload_wells = None
    if mode == "Upload Pozos_VM CSV":
        upload_wells = st.file_uploader("Upload Pozos_VM CSV", type="csv")
    permits_file = st.file_uploader("Upload permit / environmental notices CSV", type="csv")
    max_features = st.number_input("Max WFS records; 0 = all", min_value=0, max_value=50000, value=0, step=1000)

try:
    if mode == "Live Neuquen WFS":
        vm = load_wfs_csv(LAYER_POZOS_VM, None if max_features == 0 else max_features)
    else:
        if upload_wells is None:
            st.warning("Upload Pozos_VM CSV to continue.")
            st.stop()
        vm = pd.read_csv(upload_wells)
except Exception as e:
    st.error(f"Could not load Neuquen WFS / CSV: {e}")
    st.stop()

vm = norm(vm)

operator_col = find_col(vm, ["OPERADOR", "OPERATOR"])
area_col = find_col(vm, ["AREA_LEGAL", "FIELD_NAME", "YACIMIENTO", "AREA"])
state_col = find_col(vm, ["ESTADO_GIS", "ESTADO", "ORIGINAL_STATUS"])
lat_col = find_col(vm, ["LATITUD", "LATITUDE"])
lon_col = find_col(vm, ["LONGITUD", "LONGITUDE"])
year_col = find_col(vm, ["AÑO_PERF", "ANO_PERF", "YEAR_PERF"])
well_col = find_col(vm, ["WELL_NAME", "WELL_S_NAME", "UWI_NQN"])

k1, k2, k3, k4 = st.columns(4)
k1.metric("VM wells", f"{len(vm):,}")
k2.metric("Operators", vm[operator_col].nunique() if operator_col else "n/a")
k3.metric("Areas / fields", vm[area_col].nunique() if area_col else "n/a")
k4.metric("Refreshed", datetime.now().strftime("%Y-%m-%d %H:%M"))

tabs = st.tabs(["Executive Summary", "Map", "Operators / Areas", "Permit Pipeline", "Scoring Model"])

with tabs[0]:
    st.subheader("Executive Summary")
    if operator_col:
        op = vm.groupby(operator_col).size().reset_index(name="VM_WELLS").sort_values("VM_WELLS", ascending=False)
        st.dataframe(op, use_container_width=True)
        st.plotly_chart(px.bar(op.head(15), x=operator_col, y="VM_WELLS", title="Top VM operators"), use_container_width=True)

with tabs[1]:
    st.subheader("VM Wells Map")
    if lat_col and lon_col:
        m = vm.copy()
        m[lat_col] = pd.to_numeric(m[lat_col], errors="coerce")
        m[lon_col] = pd.to_numeric(m[lon_col], errors="coerce")
        m = m.dropna(subset=[lat_col, lon_col])
        hover = [c for c in [well_col, operator_col, area_col, state_col, year_col] if c]
        fig = px.scatter_mapbox(
            m, lat=lat_col, lon=lon_col, color=operator_col if operator_col else state_col,
            hover_data=hover, zoom=7.5, height=720, mapbox_style="open-street-map",
            title="Vaca Muerta wells by operator"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Latitude/longitude fields were not detected.")

with tabs[2]:
    st.subheader("Operators and areas")
    if operator_col and area_col:
        agg_dict = {"VM_WELLS": (area_col, "size")}
        if state_col:
            agg_dict["STATES"] = (state_col, lambda x: ", ".join(sorted(set(map(str, x.dropna().unique())))[:8]))
        if year_col:
            agg_dict["FIRST_YEAR"] = (year_col, "min")
            agg_dict["LAST_YEAR"] = (year_col, "max")
        summary = vm.groupby([operator_col, area_col]).agg(**agg_dict).reset_index().sort_values("VM_WELLS", ascending=False)
        st.dataframe(summary, use_container_width=True)

with tabs[3]:
    st.subheader("Forward-looking permit pipeline")
    st.write("Upload a CSV with: PUBLICATION_DATE, OPERATOR, AREA, PAD_OR_WELLS, PERMITTED_WELLS, PERMIT_STATUS, SOURCE_URL, NOTES.")
    if permits_file:
        p = pd.read_csv(permits_file)
        p.columns = [str(c).strip().upper() for c in p.columns]
        if "PUBLICATION_DATE" in p.columns:
            p["PUBLICATION_DATE"] = pd.to_datetime(p["PUBLICATION_DATE"], errors="coerce")
            p["DAYS_SINCE_PUBLICATION"] = (pd.Timestamp.today().normalize() - p["PUBLICATION_DATE"]).dt.days
        else:
            p["DAYS_SINCE_PUBLICATION"] = 999
        if "RESERVOIR" not in p.columns:
            p["RESERVOIR"] = "Unconventional"
        if "WELL_TYPE" not in p.columns:
            p["WELL_TYPE"] = "Horizontal / probable"
        p["RIG_OPPORTUNITY_SCORE"] = p.apply(score_permit, axis=1)
        p["COMMERCIAL_PRIORITY"] = p["RIG_OPPORTUNITY_SCORE"].apply(priority)
        st.dataframe(p.sort_values("RIG_OPPORTUNITY_SCORE", ascending=False), use_container_width=True)
        st.download_button("Download scored pipeline CSV", p.to_csv(index=False).encode("utf-8"), "scored_pipeline.csv", "text/csv")
    else:
        st.info("No permit CSV uploaded. Use the included permits_template.csv as a starting point.")

with tabs[4]:
    st.subheader("Rig opportunity scoring")
    st.markdown("""
    Score 0-100:
    - 40 pts: permit/environmental license status
    - 20 pts: number of permitted wells
    - 15 pts: horizontal/PAD signal
    - 10 pts: unconventional reservoir
    - 15 pts: publication recency

    Priority:
    - 80-100: Tier 1
    - 60-79: Tier 2
    - 40-59: Tier 3
    - <40: Low
    """)
