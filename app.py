from pathlib import Path
import hashlib

import pandas as pd
import streamlit as st

try:
    import folium
    from folium.plugins import Fullscreen, MiniMap, MeasureControl, MousePosition
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
    initial_sidebar_state="collapsed",
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
    hidden_cols = ["score_definition", "_score_definition", "internal_score_definition"]
    return df.drop(columns=[c for c in hidden_cols if c in df.columns])


def to_num(df: pd.DataFrame, col: str, default: float = 0) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(default)
    return pd.Series([default] * len(df))


def stable_color(name: str) -> str:
    palette = [
        "#1769E8", "#21A64A", "#FF7A00", "#9C27D3", "#FFC400",
        "#00A9B8", "#E53935", "#EC2F8C", "#5066C8", "#7A7A7A",
        "#00B894", "#F4511E", "#3949AB", "#43A047",
    ]
    if not isinstance(name, str) or not name.strip():
        return "#7A7A7A"
    idx = int(hashlib.md5(name.upper().encode("utf-8")).hexdigest(), 16) % len(palette)
    return palette[idx]


def score_to_radius(score: float) -> int:
    try:
        score = float(score)
    except Exception:
        score = 40
    score = max(10, min(score, 100))
    return int(16 + (score / 100) * 30)


def score_priority(score: float) -> str:
    try:
        score = float(score)
    except Exception:
        return "Unknown"
    if score >= 85:
        return "Strategic"
    if score >= 70:
        return "High"
    if score >= 50:
        return "Medium"
    return "Low"


def score_marker_html(score, color):
    radius = score_to_radius(score)
    diameter = radius * 2
    font_size = max(13, int(radius * 0.72))
    try:
        label = int(round(float(score)))
    except Exception:
        label = score
    return f"""
    <div style="
        width:{diameter}px;height:{diameter}px;border-radius:50%;
        background:{color};border:3px solid white;
        box-shadow:0 0 0 2px rgba(0,0,0,.18), 0 6px 18px rgba(0,0,0,.38);
        display:flex;align-items:center;justify-content:center;
        color:white;font-weight:800;font-size:{font_size}px;
        font-family:Inter,Arial,sans-serif;text-shadow:0 1px 3px rgba(0,0,0,.55);">
        {label}
    </div>
    """


def build_scored_area_df(areas, operator_area_forecast, operator_forecast):
    if not operator_area_forecast.empty and {"lat", "lon"}.issubset(operator_area_forecast.columns):
        df = operator_area_forecast.copy()
        if "rig_demand_score" not in df.columns:
            df["rig_demand_score"] = 50
        if "operator" not in df.columns:
            df["operator"] = "Unknown"
        if "area" not in df.columns:
            df["area"] = ""
        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
        df["rig_demand_score"] = pd.to_numeric(df["rig_demand_score"], errors="coerce").fillna(50)
        return df.dropna(subset=["lat", "lon"])

    if areas.empty or not {"lat", "lon"}.issubset(areas.columns):
        return pd.DataFrame()
    df = areas.copy()
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"])
    if not operator_forecast.empty and "operator" in operator_forecast.columns:
        f = clean_table(operator_forecast).copy()
        if "rig_demand_score" in f.columns:
            f["rig_demand_score"] = pd.to_numeric(f["rig_demand_score"], errors="coerce")
            df = df.merge(f[["operator", "rig_demand_score"]].dropna().drop_duplicates("operator"), on="operator", how="left")
    if "rig_demand_score" not in df.columns:
        df["rig_demand_score"] = pd.to_numeric(df.get("confidence", 45), errors="coerce").fillna(45)
    else:
        df["rig_demand_score"] = df["rig_demand_score"].fillna(pd.to_numeric(df.get("confidence", 45), errors="coerce").fillna(45))
    return df


st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] { background:#07131f; }
.block-container { padding-top:.8rem; padding-left:1rem; padding-right:1rem; max-width:100%; }
header[data-testid="stHeader"] { background:rgba(4,16,28,.92); border-bottom:1px solid rgba(255,255,255,.08); }
.ueip-topbar { background:linear-gradient(90deg,#061321,#0b1f33); color:white; border-radius:0 0 14px 14px; padding:14px 18px; margin-bottom:14px; display:flex; align-items:center; justify-content:space-between; box-shadow:0 8px 22px rgba(0,0,0,.28); }
.ueip-brand { display:flex; align-items:center; gap:12px; font-family:Inter,Arial,sans-serif; }
.ueip-logo { width:42px; height:42px; border-radius:12px; background:#fff; color:#0b1f33; display:flex; align-items:center; justify-content:center; font-size:22px; font-weight:900; }
.ueip-title-main { font-size:25px; font-weight:900; letter-spacing:.5px; line-height:1.05; }
.ueip-title-sub { font-size:12px; color:#a9bdd2; letter-spacing:1.8px; font-weight:700; }
.ueip-pill { background:rgba(23,105,232,.18); color:#dcecff; padding:8px 12px; border:1px solid rgba(69,149,255,.35); border-radius:999px; font-size:13px; font-weight:650; }
div[data-testid="stTabs"] button { color:#d6e2ee; font-weight:700; }
div[data-testid="stTabs"] button[aria-selected="true"] { color:white; border-bottom-color:#1f8bff; }
.ueip-panel { background:linear-gradient(180deg,#0b1f33,#071827); color:white; border-radius:14px; padding:16px; border:1px solid rgba(255,255,255,.08); box-shadow:0 12px 25px rgba(0,0,0,.25); height:820px; overflow-y:auto; }
.ueip-panel h3 { margin-top:0; font-size:16px; letter-spacing:.4px; }
.operator-row { display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,.08); padding:10px 0; gap:8px; }
.operator-left { display:flex; align-items:center; gap:10px; }
.operator-check { width:18px; height:18px; border-radius:4px; display:inline-flex; align-items:center; justify-content:center; color:white; font-size:12px; font-weight:900; }
.operator-name { font-size:14px; font-weight:750; }
.operator-label { font-size:11px; color:#9eb1c6; }
.operator-score { width:34px; height:34px; border-radius:50%; color:white; font-size:13px; font-weight:900; display:flex; align-items:center; justify-content:center; border:2px solid rgba(255,255,255,.7); box-shadow:0 4px 10px rgba(0,0,0,.25); }
.score-legend { margin-top:18px; background:rgba(255,255,255,.04); border-radius:12px; padding:14px; border:1px solid rgba(255,255,255,.08); }
.score-dots { display:flex; justify-content:space-between; align-items:end; margin-top:14px; }
.legend-dot { border-radius:50%; background:#d8dee6; border:2px solid rgba(255,255,255,.65); }
.ueip-map-wrap { border-radius:14px; overflow:hidden; border:1px solid rgba(255,255,255,.10); box-shadow:0 12px 28px rgba(0,0,0,.38); }
.score-card { background:white; color:#122033; border-radius:14px; padding:18px 20px; border:1px solid rgba(0,0,0,.08); box-shadow:0 8px 20px rgba(0,0,0,.12); }
.score-card table { width:100%; border-collapse:collapse; }
.score-card th,.score-card td { padding:9px 10px; border-bottom:1px solid #e9edf2; }
.score-card th { text-align:left; color:#2c3b4d; }
.score-card td:last-child,.score-card th:last-child { text-align:right; font-weight:800; }
.info-note { background:rgba(255,255,255,.92); color:#172638; padding:12px 14px; border-radius:12px; border:1px solid rgba(0,0,0,.08); font-weight:600; font-size:13px; }
.stDataFrame { border-radius:12px; overflow:hidden; }
</style>
""", unsafe_allow_html=True)

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
gis_layers = load_csv("gis_layer_registry.csv")

st.markdown("""
<div class="ueip-topbar">
  <div class="ueip-brand"><div class="ueip-logo">◆</div><div><div class="ueip-title-main">ULTRACORE</div><div class="ueip-title-sub">ENERGY INTELLIGENCE</div></div></div>
  <div class="ueip-pill">Argentina-first · LATAM-ready · GIS Intelligence</div>
</div>
""", unsafe_allow_html=True)

tabs = st.tabs(["Executive Summary", "Immersive GIS Map", "Operator Intelligence", "Area Intelligence", "Permit Pipeline", "Rig Coverage", "Multi-Service", "Score", "Data Export"])

with tabs[0]:
    st.header("Executive Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Countries", len(countries)); c2.metric("Basins", len(basins)); c3.metric("Areas / blocks", len(areas)); c4.metric("Operators", len(operators))
    st.markdown("""**Objective:** identify future commercial opportunities for Ultracore by crossing regulatory signals, EIA permits, investor plans, media/LinkedIn intelligence, rig contracts, provider coverage and multi-service demand.

**Core question:** what operator, in what basin and area, will need which service, when, and who is the incumbent provider?""")
    if not operator_forecast.empty:
        df = clean_table(operator_forecast)
        st.subheader("Top Operator Rig Demand Ranking")
        st.dataframe(df, use_container_width=True)
        if px is not None and {"operator", "rig_demand_score"}.issubset(df.columns):
            chart_df = df.copy(); chart_df["rig_demand_score"] = to_num(chart_df, "rig_demand_score")
            fig = px.bar(chart_df.sort_values("rig_demand_score", ascending=True), x="rig_demand_score", y="operator", orientation="h", title="Rig Demand Score by Operator")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("operator_forecast.csv not found yet. Run the investor workflow.")

with tabs[1]:
    scored_df = build_scored_area_df(areas, operator_area_forecast, operator_forecast)
    left, right = st.columns([1.05, 5.2], gap="small")
    with left:
        st.markdown('<div class="ueip-panel">', unsafe_allow_html=True)
        st.markdown("### OPERATOR LEGEND")
        st.caption("Color = operator · Circle size = Drill / Rig Demand Score")
        if not scored_df.empty:
            op_score = scored_df.groupby("operator", dropna=False)["rig_demand_score"].max().reset_index().sort_values("rig_demand_score", ascending=False)
            for _, row in op_score.head(18).iterrows():
                op = str(row["operator"]); score = float(row["rig_demand_score"]); color = stable_color(op)
                st.markdown(f"""
                <div class="operator-row"><div class="operator-left"><div class="operator-check" style="background:{color};">✓</div><div><div class="operator-name">{op}</div><div class="operator-label">{score_priority(score)} · Drill Score</div></div></div><div class="operator-score" style="background:{color};">{int(round(score))}</div></div>
                """, unsafe_allow_html=True)
        else:
            st.info("No scored area data available yet.")
        st.markdown("""
        <div class="score-legend"><b>SCORE VISUALIZATION</b><br><span style="font-size:12px;color:#9eb1c6;">Circle size is proportional to Drill Score</span><div class="score-dots"><div><div class="legend-dot" style="width:12px;height:12px;"></div><small>20</small></div><div><div class="legend-dot" style="width:18px;height:18px;"></div><small>40</small></div><div><div class="legend-dot" style="width:25px;height:25px;"></div><small>60</small></div><div><div class="legend-dot" style="width:34px;height:34px;"></div><small>80</small></div><div><div class="legend-dot" style="width:46px;height:46px;"></div><small>100</small></div></div></div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        if folium is None or st_folium is None:
            st.error("folium or streamlit-folium is not installed. Check requirements.txt.")
        else:
            map_center = [-38.5, -68.8]
            if not scored_df.empty and {"lat", "lon"}.issubset(scored_df.columns):
                lat_med = pd.to_numeric(scored_df["lat"], errors="coerce").dropna(); lon_med = pd.to_numeric(scored_df["lon"], errors="coerce").dropna()
                if not lat_med.empty and not lon_med.empty:
                    map_center = [float(lat_med.median()), float(lon_med.median())]
            m = folium.Map(location=map_center, zoom_start=6, tiles=None, control_scale=True, prefer_canvas=True)
            folium.TileLayer("OpenStreetMap", name="OpenStreetMap / roads", control=True, show=True).add_to(m)
            folium.TileLayer(tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr="Esri", name="Satellite / Esri World Imagery", control=True, show=False).add_to(m)
            folium.TileLayer(tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}", attr="Esri", name="Topographic / Esri", control=True, show=False).add_to(m)
            if not gis_layers.empty and {"url", "layer_id", "layer_name"}.issubset(gis_layers.columns):
                for _, lyr in gis_layers.iterrows():
                    try:
                        folium.raster_layers.WmsTileLayer(url=str(lyr["url"]), layers=str(lyr["layer_id"]), name=f"{lyr.get('province', '')} - {lyr.get('layer_name', lyr['layer_id'])}", fmt="image/png", transparent=True, version=str(lyr.get("version", "1.1.1")), overlay=True, control=True, show=False).add_to(m)
                    except Exception:
                        pass
            else:
                neuquen_wms = "https://hidrocarburos.energianeuquen.gob.ar/geoserver/wms"
                for layer_name, display_name, show in [("Hidrocarburos:Areas", "Neuquen - Areas / concessions", True), ("Hidrocarburos:Pozos_VM", "Neuquen - Vaca Muerta wells", True), ("Hidrocarburos:Pozos", "Neuquen - Wells", False), ("Hidrocarburos:Ductos", "Neuquen - Ducts", False), ("Hidrocarburos:Instalaciones", "Neuquen - Facilities", False), ("Hidrocarburos:Locaciones", "Neuquen - Locations", False)]:
                    try:
                        folium.raster_layers.WmsTileLayer(url=neuquen_wms, layers=layer_name, name=display_name, fmt="image/png", transparent=True, version="1.1.1", overlay=True, control=True, show=show).add_to(m)
                    except Exception:
                        pass
            if not scored_df.empty and {"lat", "lon"}.issubset(scored_df.columns):
                df_map = scored_df.copy(); df_map["lat"] = pd.to_numeric(df_map["lat"], errors="coerce"); df_map["lon"] = pd.to_numeric(df_map["lon"], errors="coerce"); df_map["rig_demand_score"] = pd.to_numeric(df_map["rig_demand_score"], errors="coerce").fillna(50); df_map = df_map.dropna(subset=["lat", "lon"])
                fg = folium.FeatureGroup(name="UEIP scored areas by operator", show=True)
                for _, row in df_map.iterrows():
                    op = str(row.get("operator", "Unknown")); area = str(row.get("area", "")); score = float(row.get("rig_demand_score", 50)); color = stable_color(op); radius = score_to_radius(score)
                    popup_html = f"""<div style="font-family:Inter,Arial,sans-serif;min-width:260px;"><h3 style="margin:0 0 8px 0;">{area}</h3><b>Operator:</b> {op}<br><b>Drill / Rig Demand Score:</b> {int(round(score))}<br><b>Priority:</b> {score_priority(score)}<br><b>Basin:</b> {row.get('basin', '')}<br><b>Province:</b> {row.get('province', '')}<br><b>Signals:</b> {row.get('signals', '')}<br><b>Provider / coverage:</b> {row.get('provider', row.get('coverage_type', 'To verify'))}<br></div>"""
                    folium.Marker(location=[row["lat"], row["lon"]], tooltip=f"{op} · {area} · Score {int(round(score))}", popup=folium.Popup(popup_html, max_width=420), icon=folium.DivIcon(html=score_marker_html(score, color), icon_size=(radius * 2, radius * 2), icon_anchor=(radius, radius))).add_to(fg)
                fg.add_to(m)
            Fullscreen(position="topright").add_to(m); MiniMap(toggle_display=True, position="bottomleft").add_to(m); MeasureControl(position="topleft").add_to(m); MousePosition(position="bottomright", separator=" | ", prefix="Lat/Lon:", num_digits=5).add_to(m); folium.LayerControl(collapsed=False).add_to(m)
            st.markdown('<div class="ueip-map-wrap">', unsafe_allow_html=True); st_folium(m, width=None, height=820); st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('<div class="info-note">Zoom in to see blocks, wells, roads, towns and facilities. Click a colored score circle to open operator, area and score details. Use the layer control to turn official GIS layers on/off.</div>', unsafe_allow_html=True)

with tabs[2]:
    st.header("Operator Intelligence")
    st.markdown("""<div class="score-card"><b>Score Composition</b><table><tr><th>Score Component</th><th>Weight</th></tr><tr><td>Permits / EIA</td><td>40%</td></tr><tr><td>Investor / CAPEX Signal</td><td>30%</td></tr><tr><td>Activity Intensity</td><td>20%</td></tr><tr><td>Operator Tier / Core Relevance</td><td>10%</td></tr></table></div>""", unsafe_allow_html=True)
    if not operator_forecast.empty:
        st.dataframe(clean_table(operator_forecast), use_container_width=True)
    else:
        st.info("operator_forecast.csv not found yet.")
    if not operator_signals.empty:
        st.subheader("Underlying Signals"); st.dataframe(clean_table(operator_signals), use_container_width=True)

with tabs[3]:
    st.header("Area Intelligence")
    if not operator_area_forecast.empty:
        st.dataframe(clean_table(operator_area_forecast), use_container_width=True)
    else:
        st.info("operator_area_forecast.csv not found yet.")
    if not areas.empty:
        st.subheader("National Area Master"); st.dataframe(clean_table(areas), use_container_width=True)

with tabs[4]:
    st.header("Permit Pipeline")
    if not permits_pipeline.empty:
        st.dataframe(clean_table(permits_pipeline), use_container_width=True)
    else:
        st.info("permits_pipeline_auto.csv not found yet.")
    if not changes_log.empty:
        st.subheader("Changes Log"); st.dataframe(clean_table(changes_log), use_container_width=True)

with tabs[5]:
    st.header("Rig Coverage / Operator Rig Strategy")
    st.markdown("This layer tracks whether demand is already covered by owned rigs, leased rigs or third-party operated contracts. It is critical for estimating **Open Rig Opportunity Score**.")
    if not rig_strategy.empty:
        st.dataframe(clean_table(rig_strategy), use_container_width=True)
    if not providers.empty:
        st.subheader("Rig and Service Providers"); st.dataframe(clean_table(providers), use_container_width=True)

with tabs[6]:
    st.header("Multi-Service Opportunity Layer")
    st.markdown("Ultracore opportunities are not limited to drilling rigs. Services tracked: drilling rigs, workover, frac, e-frac, venting/gas recovery, HVAC, lighting towers, power generation, water management, facilities and midstream.")
    if not services.empty:
        st.subheader("Service Master"); st.dataframe(clean_table(services), use_container_width=True)
    if not service_rules.empty:
        st.subheader("Service Opportunity Rules"); st.dataframe(clean_table(service_rules), use_container_width=True)

with tabs[7]:
    st.header("Score Composition")
    st.markdown("""<div class="score-card"><h3>Rig Demand Score</h3><table><tr><th>Score Component</th><th>Weight</th></tr><tr><td>Permits / EIA</td><td>40%</td></tr><tr><td>Investor / CAPEX Signal</td><td>30%</td></tr><tr><td>Activity Intensity</td><td>20%</td></tr><tr><td>Operator Tier / Core Relevance</td><td>10%</td></tr></table><p>The score estimates the probability that an operator will require drilling rigs or associated services within the next 6–18 months.</p><h3>Rig Coverage Score</h3><p>Measures whether the operator's demand appears already covered by owned rigs, leased rigs or third-party contractors.</p><h3>Open Rig Opportunity Score</h3><p>Demand not yet covered by known rig capacity.</p><h3>Multi-Service Score</h3><p>Extends the opportunity model beyond rigs into workover, frac, e-frac, venting, HVAC, lighting, power, water and facilities.</p></div>""", unsafe_allow_html=True)

with tabs[8]:
    st.header("Data Export")
    export_items = {"operator_forecast.csv": operator_forecast, "operator_signals.csv": operator_signals, "operator_area_forecast.csv": operator_area_forecast, "permits_pipeline_auto.csv": permits_pipeline, "countries.csv": countries, "basin_master.csv": basins, "province_master.csv": provinces, "operator_master.csv": operators, "area_master.csv": areas, "service_master.csv": services, "rig_provider_master.csv": providers, "operator_rig_strategy.csv": rig_strategy, "score_definitions.csv": score_definitions, "gis_layer_registry.csv": gis_layers}
    for filename, df in export_items.items():
        if not df.empty:
            st.download_button(label=f"Download {filename}", data=clean_table(df).to_csv(index=False).encode("utf-8"), file_name=filename, mime="text/csv")


