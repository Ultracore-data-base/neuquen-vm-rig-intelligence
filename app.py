from pathlib import Path
import hashlib
import pandas as pd
import streamlit as st
from contractor_fleet_intelligence import contractor_fleet_html
from rig_gap_intelligence import rig_gap_html
from opportunity_ranking import build_opportunity_ranking
from official_source_registry import source_summary_by_module
from energy_dataset_registry import (
    dataset_status_summary,
    rig_score_weight_table,
    critical_dataset_backlog
)
from operational_activity_engine import (
    calculate_operational_activity_score,
    activity_summary_by_operator,
    activity_summary_by_basin,
    top_operational_activity
)
from observed_activity_engine import (
    calculate_observed_activity,
    observed_activity_by_operator,
    observed_activity_by_area
)
from observed_activity_panel import observed_activity_html
from tender_probability_engine import (
    build_tender_probability,
    tender_probability_html
)
from forecast_intelligence_engine import (
    build_forecast_intelligence,
    forecast_intelligence_html
)
from rig_expansion_engine import (
    build_rig_expansion_score,
    rig_expansion_html
)
from rig_commitment_engine_v2 import (
    rig_commitment_html,
    apply_rig_commitment_penalty
)
from contract_intelligence_engine import (
    build_contract_intelligence,
    contract_intelligence_html
)
from capital_program_engine import (
    build_capital_program,
    capital_program_html
)
from capital_program_engine import (
    build_capital_program,
    capital_program_html
)

from commercial_action_engine_v2 import commercial_action_html
try:
    import folium
    from folium.plugins import Fullscreen, MiniMap, MeasureControl, MousePosition
    from streamlit_folium import st_folium
except Exception:
    folium = None
    st_folium = None
from commercial_opportunity_engine import enrich_opportunity_ranking

try:
    import plotly.express as px
except Exception:
    px = None
from official_gis_registry import (
gis_source_status,
active_wms_layers_for_province,
pending_gis_sources
)


st.set_page_config(
    page_title="Ultracore Energy Intelligence Platform",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path("data")
st.markdown("""
<style>
.selected-op {
    border: 2px solid #36A3FF !important;
    border-radius: 12px;
    padding: 9px 8px !important;
    background: rgba(54,163,255,0.18);
    box-shadow: 0 0 14px rgba(54,163,255,0.35);
}

.muted-op {
    opacity: 0.55;
    transform: scale(0.94);
    transform-origin: left center;
}

.selected-op .op-name {
    color: #ffffff !important;
    font-size: 13.5px !important;
}

.selected-op .op-score {
    transform: scale(1.12);
}
.alert-banner {
    background: rgba(54,163,255,0.18);
    border: 1px solid rgba(54,163,255,0.55);
    color: #ffffff;
    border-radius: 10px;
    padding: 8px 10px;
    font-weight: 800;
    font-size: 12px;
    margin-bottom: 8px;
    box-shadow: 0 0 14px rgba(54,163,255,0.25);
}
.opportunity-banner {
    border-radius: 10px;
    padding: 8px 10px;
    font-weight: 900;
    font-size: 12px;
    margin-bottom: 8px;
    box-shadow: 0 0 14px rgba(54,163,255,0.25);
}

.opportunity-green {
    background: rgba(39,174,96,0.22);
    border: 1px solid rgba(39,174,96,0.75);
    color: #ffffff;
}

.opportunity-blue {
    background: rgba(54,163,255,0.20);
    border: 1px solid rgba(54,163,255,0.75);
    color: #ffffff;
}

.opportunity-yellow {
    background: rgba(241,196,15,0.22);
    border: 1px solid rgba(241,196,15,0.75);
    color: #ffffff;
}
.opportunity-orange {
    background: rgba(230,126,34,0.24);
    border: 1px solid rgba(230,126,34,0.80);
    color: #ffffff;
}

.opportunity-gray {
    background: rgba(127,140,141,0.20);
    border: 1px solid rgba(127,140,141,0.60);
    color: #ffffff;
}

.service-badge-wrap {
    margin-top: 8px;
}

.service-badge{
    display:inline-block;
    background:#168BFF;
    color:white;
    border-radius:999px;
    padding:4px 10px;
    margin:3px;
    font-size:11px;
    font-weight:800;
    box-shadow:0 0 8px rgba(22,139,255,.35);
}

</style>
""", unsafe_allow_html=True)

def load_csv(name):
    path = DATA_DIR / name
    if path.exists():
        return pd.read_csv(path)
    fallback = Path(name)
    if fallback.exists():
        return pd.read_csv(fallback)
    return pd.DataFrame()


def clean_table(df):
    if df.empty:
        return df
    return df.drop(columns=[c for c in ["score_definition"] if c in df.columns])


def color_for_operator(operator):
    palette = {
        "YPF": "#1769E8",
        "VISTA": "#21A64A",
        "PAN AMERICAN": "#FF7A00",
        "PAE": "#FF7A00",
        "PAMPA": "#9C27D3",
        "PLUSPETROL": "#FFC400",
        "TECPETROL": "#00A9B8",
        "SHELL": "#E53935",
        "CGC": "#EC2F8C",
        "CHEVRON": "#2E63B8",
        "TOTAL": "#7A7A7A",
        "GEOPARK": "#21A64A",
        "DLS": "#455A64",
        "HP": "#263238",
    }
    text = str(operator).upper()
    for key, value in palette.items():
        if key in text:
            return value
    fallback = ["#1769E8", "#21A64A", "#FF7A00", "#9C27D3", "#FFC400", "#00A9B8", "#E53935", "#EC2F8C", "#2E63B8"]
    return fallback[int(hashlib.md5(text.encode()).hexdigest(), 16) % len(fallback)]


def score_radius(score):
    try:
        score = float(score)
    except Exception:
        score = 45
    score = max(15, min(score, 100))
    return int(10 + score * 0.18)


def priority(score):
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


def score_icon(score, color):
    r = score_radius(score)
    d = r * 2
    fs = max(11, int(r * 0.68))
    return f"""
    <div style="
        width:{d}px;height:{d}px;border-radius:50%;
        background:{color};border:2px solid #fff;
        box-shadow:0 5px 12px rgba(0,0,0,.36),0 0 0 1px rgba(0,0,0,.16);
        display:flex;align-items:center;justify-content:center;
        color:white;font-weight:900;font-size:{fs}px;
        font-family:Arial, sans-serif;text-shadow:0 2px 4px rgba(0,0,0,.45);
    ">{int(round(float(score)))}</div>
    """


def normalize_text(value):
    return str(value or "").strip()


def detect_basin_from_row(row):
    text = " ".join([
        normalize_text(row.get("basin", "")),
        normalize_text(row.get("province", "")),
        normalize_text(row.get("area", "")),
    ]).upper()

    if any(k in text for k in ["NEUQU", "VACA MUERTA", "LOMA CAMPANA", "AÑELO", "FORTIN DE PIEDRA", "BAJADA DEL PALO"]):
        return "Neuquén Basin"
    if any(k in text for k in ["GOLFO SAN JORGE", "CHUBUT", "SANTA CRUZ", "MANANTIALES BEHR", "CERRO DRAGON"]):
        return "Golfo San Jorge"
    if any(k in text for k in ["AUSTRAL", "TIERRA DEL FUEGO", "CUENCA AUSTRAL"]):
        return "Austral Basin"
    if any(k in text for k in ["CUYANA", "MENDOZA", "LLANCANELO", "CACHEUTA"]):
        return "Cuyana Basin"
    if any(k in text for k in ["NOROESTE", "NOA", "SALTA", "JUJUY", "FORMOSA"]):
        return "Northwest Basin"
    if any(k in text for k in ["OFFSHORE", "MAR ARGENTINO", "CAN_", "MLO_", "AUS_"]):
        return "Argentina Offshore"
    return normalize_text(row.get("basin", "")) or "Argentina"


def layer_context_for_basin(basin):
    b = str(basin).lower()
    if "neuqu" in b:
        return {
            "zone": "Neuquén / Cuenca Neuquina",
            "official": [
                ("Areas / concessions", True),
                ("Vaca Muerta wells", True),
                ("Wells", False),
                ("Ducts", False),
                ("Facilities", False),
                ("Locations", False),
            ],
            "focus": "Vaca Muerta / unconventional + conventional activity",
        }
    if "golfo" in b or "jorge" in b:
        return {
            "zone": "Chubut / Santa Cruz / Golfo San Jorge",
            "official": [
                ("Chubut areas / concessions", True),
                ("Santa Cruz areas / concessions", True),
                ("Wells", True),
                ("Batteries / facilities", False),
                ("Pipelines / evacuation", False),
                ("Service bases", False),
            ],
            "focus": "Mature fields, workover, pulling, secondary recovery and drilling campaigns",
        }
    if "austral" in b:
        return {
            "zone": "Santa Cruz / Tierra del Fuego / Austral",
            "official": [
                ("Austral concessions", True),
                ("Gas fields", True),
                ("Wells", False),
                ("Pipelines", False),
                ("Compression / facilities", False),
                ("Offshore support", False),
            ],
            "focus": "Gas, offshore/onshore logistics and field redevelopment",
        }
    if "cuyana" in b:
        return {
            "zone": "Mendoza / Cuenca Cuyana",
            "official": [
                ("Mendoza areas / concessions", True),
                ("Wells", True),
                ("Ducts", False),
                ("Facilities", False),
                ("Access roads", False),
                ("Service bases", False),
            ],
            "focus": "Conventional oil, mature-field drilling and workover",
        }
    if "northwest" in b or "noroeste" in b:
        return {
            "zone": "NOA / Northwest Basin",
            "official": [
                ("NOA concessions", True),
                ("Gas fields", True),
                ("Wells", False),
                ("Pipelines", False),
                ("Facilities", False),
                ("Access routes", False),
            ],
            "focus": "Gas and conventional exploration / redevelopment",
        }
    if "offshore" in b:
        return {
            "zone": "Argentina Offshore",
            "official": [
                ("Offshore blocks", True),
                ("Seismic 2D / 3D", True),
                ("Exploration wells", False),
                ("Ports / logistics", False),
                ("Marine support", False),
                ("Environmental studies", False),
            ],
            "focus": "Exploration, seismic, offshore logistics and long-term services",
        }
    return {
        "zone": "Argentina / Upstream",
        "official": [
            ("Areas / concessions", True),
            ("Wells", True),
            ("Ducts", False),
            ("Facilities", False),
            ("Basins", True),
            ("Service bases", False),
        ],
        "focus": "National upstream opportunity screening",
    }


def forecast_rigs(score):
    try:
        score = float(score)
    except Exception:
        score = 50
    if score >= 90:
        return "2–4 rigs"
    if score >= 80:
        return "1–3 rigs"
    if score >= 70:
        return "1–2 rigs"
    if score >= 55:
        return "watchlist / 0–1 rig"
    return "low probability"


def multi_service_tags(score, basin):
    try:
        score = float(score)
    except Exception:
        score = 50
    tags = []
    b = str(basin).lower()
    if score >= 55:
        tags.extend(["Workover", "Lighting Towers"])
    if score >= 70:
        tags.extend(["HVAC", "Venting"])
    if score >= 82 and ("neuqu" in b or "vaca" in b):
        tags.append("E-Frac")
    if "golfo" in b or "cuyana" in b:
        tags.append("Pulling / mature-field services")
    return tags or ["Monitoring"]
def contractor_context_for_operator(operator):
    if contractor_intelligence.empty:
        return None

    if "operator" not in contractor_intelligence.columns:
        return None

    op = str(operator).strip().upper()

    matches = contractor_intelligence[
        contractor_intelligence["operator"].astype(str).str.strip().str.upper() == op
    ]

    if matches.empty:
        return None

    return matches.iloc[0].to_dict()

def build_scored_points(area_master, area_forecast, op_forecast):
    if not area_forecast.empty and {"lat", "lon"}.issubset(area_forecast.columns):
        df = area_forecast.copy()
        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
        if "rig_demand_score" not in df.columns:
            df["rig_demand_score"] = 50
        df["rig_demand_score"] = pd.to_numeric(df["rig_demand_score"], errors="coerce").fillna(50)
        if "operator" not in df.columns:
            df["operator"] = "Unknown"
        if "area" not in df.columns:
            df["area"] = ""
        df = df.dropna(subset=["lat", "lon"])
        if len(df) >= 4:
            df["detected_basin"] = df.apply(detect_basin_from_row, axis=1)
            return df

    if area_master.empty or not {"lat", "lon"}.issubset(area_master.columns):
        return pd.DataFrame()

    df = area_master.copy()
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"])

    if not op_forecast.empty and {"operator", "rig_demand_score"}.issubset(op_forecast.columns):
        f = clean_table(op_forecast).copy()
        f["rig_demand_score"] = pd.to_numeric(f["rig_demand_score"], errors="coerce")
        df = df.merge(
            f[["operator", "rig_demand_score"]].drop_duplicates("operator"),
            on="operator",
            how="left",
        )

    if "rig_demand_score" not in df.columns:
        df["rig_demand_score"] = pd.to_numeric(df.get("confidence", 50), errors="coerce").fillna(50)
    else:
        df["rig_demand_score"] = df["rig_demand_score"].fillna(
            pd.to_numeric(df.get("confidence", 50), errors="coerce").fillna(50)
        )

    df = df.reset_index(drop=True)
    for i in range(len(df)):
        df.loc[i, "lat"] = df.loc[i, "lat"] + ((i % 5) - 2) * 0.012
        df.loc[i, "lon"] = df.loc[i, "lon"] + ((i % 7) - 3) * 0.012

    df["detected_basin"] = df.apply(detect_basin_from_row, axis=1)
    return df


operator_forecast = load_csv("operator_forecast.csv")
operator_signals = load_csv("operator_signals.csv")
operator_area_forecast = load_csv("operator_area_forecast.csv")
permits_pipeline = load_csv("permits_pipeline_auto.csv")
changes_log = load_csv("changes_log.csv")
countries = load_csv("countries.csv")
basins = load_csv("basin_master.csv")
operators = load_csv("operator_master.csv")
areas = load_csv("area_master.csv")
services = load_csv("service_master.csv")
providers = load_csv("rig_provider_master.csv")
rig_strategy = load_csv("operator_rig_strategy.csv")
service_rules = load_csv("service_opportunity_rules.csv")
gis_layers = load_csv("gis_layer_registry.csv")
contractor_intelligence = load_csv("contractor_intelligence.csv")
rig_fleet = load_csv("rig_fleet_master.csv")
official_sources = load_csv("official_energy_data_sources.csv")
official_gis_layers = load_csv("official_gis_layer_registry.csv")
energy_datasets = load_csv(
    "energy_intelligence_dataset_registry.csv"
)
activity_scores = load_csv("activity_score_master.csv")
observed_activity = load_csv("observed_activity_master.csv")

rig_commitments = load_csv("rig_commitment_master_v2.csv")
scored = build_scored_points(areas, operator_area_forecast, operator_forecast)
contracts = load_csv("contract_master.csv")
capital_programs = load_csv("capital_program_master.csv")

opportunity_ranking = build_opportunity_ranking(
    scored,
    contractor_intelligence,
    forecast_rigs
)
tender_probability = build_tender_probability(
    scored,
    observed_activity,
    contractor_intelligence,
    forecast_rigs
)
forecast_intelligence = build_forecast_intelligence(
    scored,
    observed_activity,
    tender_probability
)

rig_expansion = build_rig_expansion_score(
    scored,
    observed_activity,
    tender_probability
)

rig_expansion = apply_rig_commitment_penalty(
    rig_expansion,
    rig_commitments
)
contract_intelligence = build_contract_intelligence(
    contracts,
    observed_activity,
    tender_probability,
    forecast_intelligence,
    rig_expansion
)
capital_program = build_capital_program(
    capital_programs
)
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] {background:#06111d;}
.block-container {
    padding-top: 0.35rem !important;
    padding-left: 0.35rem !important;
    padding-right: 0.35rem !important;
    padding-bottom: 0rem !important;
    max-width: 100% !important;
}
header[data-testid="stHeader"] {background:rgba(5,15,26,.96);}
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {display:none !important;}

div[data-testid="stVerticalBlock"] {gap:0.25rem !important;}
div[data-testid="stHorizontalBlock"] {gap:0.25rem !important;}

div[data-testid="stTabs"] button {
    color:#e5f0ff !important;
    font-weight:800 !important;
    opacity:1 !important;
}
div[data-testid="stTabs"] button p {
    color:#e5f0ff !important;
    opacity:1 !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color:#ffffff !important;
    border-bottom:3px solid #168BFF !important;
}

.uc-title {
    background:#061321;
    color:white;
    padding:10px 14px;
    border-bottom:1px solid rgba(255,255,255,.10);
    font-size:20px;
    font-weight:900;
    letter-spacing:.5px;
}
.uc-title span {
    display:block;
    font-size:9px;
    color:#9fb4c8;
    letter-spacing:1.6px;
    margin-top:2px;
}

.panel-shell{
  background:linear-gradient(180deg,#092034,#061321);
  color:white;
  height:760px;
  overflow-y:auto;
  padding:13px 12px;
  border:1px solid rgba(255,255,255,.08);
  box-sizing:border-box;
}
.right-panel{
    background:linear-gradient(180deg,#092034,#061321);
    color:#ffffff;
    height:760px;
    overflow-y:auto;
    padding:13px 12px;
    border:1px solid rgba(255,255,255,.08);
    box-sizing:border-box;
}
.panel-title{font-size:14px;font-weight:900;letter-spacing:.5px;margin-bottom:8px;}
.panel-subtitle{font-size:12.5px;color:#b6c6d6;margin-bottom:8px;}
.right-panel .panel-subtitle{color:#9fb4c8;}

.op-row{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid rgba(255,255,255,.09);padding:7px 0;}
.op-left{display:flex;align-items:center;gap:9px;}
.op-check{width:17px;height:17px;border-radius:4px;color:white;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:900;flex-shrink:0;}
.op-name{font-weight:800;font-size:12.5px;color:#edf5ff;}
.op-sub{font-size:10.5px;color:#9fb4c8;}
.op-score{width:30px;height:30px;border-radius:50%;color:white;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:900;border:2px solid rgba(255,255,255,.75);flex-shrink:0;}

.layer-row{display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid rgba(0,0,0,.08);font-size:12.5px;font-weight:750;}
.layer-box{width:16px;height:16px;border-radius:3px;background:#168BFF;color:white;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:900;}
.layer-box.off{background:white;color:#677383;border:1px solid #aeb8c3;}
.layer-group-title{margin-top:12px;margin-bottom:4px;font-size:11px;font-weight:900;color:#526173;letter-spacing:.7px;}
.layer-select{background:white;border:1px solid #c9d3dc;border-radius:6px;padding:7px 8px;margin:6px 0;font-size:12px;color:#122033;}

.detail-card{
    margin-top:10px;
    padding:10px;
    background:rgba(22,139,255,0.12);
    border:1px solid rgba(54,163,255,0.35);
    border-radius:10px;
    color:#d8e6ff;
    font-size:11px;
    line-height:1.5;
}

.detail-card b{
    color:#36a3ff;
    font-size:12px;
    display:block;
    margin-bottom:6px;
}
.detail-row span:last-child{
    color:#36a3ff;
    font-weight:800;
}
.detail-row span:first-child{
    min-width:92px;
    padding-right:8px;
}
.detail-card{
    margin-top:8px;
    padding:8px;
    background:rgba(22,139,255,.12);
    border:1px solid rgba(22,139,255,.35);
    border-radius:8px;
    font-size:11px;
    line-height:1.5;
    color:#d8e6ff;
}
.detail-pill{display:inline-block;background:#168BFF;color:white;border-radius:999px;padding:3px 7px;margin:3px 3px 0 0;font-size:11px;font-weight:800;}

iframe {display:block !important;}
.uc-footer{
  height:32px;line-height:32px;background:#061321;color:#fff;
  padding:0 14px;font-size:13px;font-weight:750;border-top:1px solid rgba(255,255,255,.08);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.uc-score-card{
  background:white;color:#172638;border-radius:14px;padding:18px 20px;margin:14px 18px;
  box-shadow:0 8px 22px rgba(0,0,0,.18);
}
.uc-score-card table{width:100%;border-collapse:collapse;}
.uc-score-card th,.uc-score-card td{padding:9px;border-bottom:1px solid #e6ebf0;}
.uc-score-card td:last-child,.uc-score-card th:last-child{text-align:right;font-weight:900;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="uc-title">ULTRACORE<span>ENERGY INTELLIGENCE</span></div>', unsafe_allow_html=True)

tabs = st.tabs([
    "Executive Summary",
    "Immersive GIS Map",
    "Operator Intelligence",
    "Rig Opportunities",
    "Commercial Targets",
    "Area Intelligence",
    "Permit Pipeline",
    "Rig Coverage",
    "Multi-Service",
    "Operational Activity",
    "Score",
    "Official Data",
    "Capital Program",
    "Data Export",
])


with tabs[0]:
    st.markdown('<div style="padding:18px;color:white;">', unsafe_allow_html=True)
    st.header("Ultracore Energy Intelligence Platform")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Countries", len(countries))
    c2.metric("Basins", len(basins))
    c3.metric("Areas / blocks", len(areas))
    c4.metric("Operators", len(operators))
    if not operator_forecast.empty:
        st.subheader("Top Operator Rig Demand Ranking")
        st.dataframe(clean_table(operator_forecast), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)


with tabs[1]:
    left_col, map_col, right_col = st.columns([1.05, 4.65, 1.05], gap="small")

    with left_col:
        op_rows = ""
        if not scored.empty:
            op_scores = (
                scored.groupby("operator", dropna=False)["rig_demand_score"]
                .max()
                .reset_index()
                .sort_values("rig_demand_score", ascending=False)
            )           
            for _, row in op_scores.head(18).iterrows():
                op = str(row["operator"])
                score = float(row["rig_demand_score"])
                color = color_for_operator(op)

                row_class = "op-row"
                op_rows += f"""
                <div class="{row_class}">
                  <div class="op-left">
                    <div class="op-check" style="background:{color};">✓</div>
                    <div>
                      <div class="op-name">{op}</div>
                      <div class="op-sub">Score</div>
                    </div>
                  </div>
                  <div class="op-score" style="background:{color};">{int(round(score))}</div>
                </div>
                """
        else:
            op_rows = "<div style='color:#b6c6d6;font-size:13px;'>No scored areas yet.</div>"
           
        st.html(f"""
        <div class="panel-shell">
          <div class="panel-title">OPERATOR LEGEND ⓘ</div>
          <div class="panel-subtitle">Show / Hide all operators</div>
          {op_rows}
        </div>
        """)

    with map_col:
        selected_label = "Argentina › Neuquén Basin › Vaca Muerta"
        selected_row = None

        if folium is None or st_folium is None:
            st.error("folium / streamlit-folium missing")
        else:
            center = [-38.55, -68.75]
            zoom = 8

            if not scored.empty and {"lat", "lon"}.issubset(scored.columns):
                use = scored
                if "province" in scored.columns:
                    neuq = scored[scored["province"].astype(str).str.contains("Neuquen|Neuquén", case=False, na=False)]
                    if not neuq.empty:
                        use = neuq
                lat_series = pd.to_numeric(use["lat"], errors="coerce").dropna()
                lon_series = pd.to_numeric(use["lon"], errors="coerce").dropna()
                if not lat_series.empty and not lon_series.empty:
                    center = [float(lat_series.median()), float(lon_series.median())]

            m = folium.Map(location=center, zoom_start=zoom, tiles=None, control_scale=True, prefer_canvas=True)

            folium.TileLayer("OpenStreetMap", name="OpenStreetMap / roads", show=True).add_to(m)
            folium.TileLayer(
                tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                attr="Esri",
                name="Satellite / Esri World Imagery",
                show=False,
            ).add_to(m)
            folium.TileLayer(
                tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
                attr="Esri",
                name="Topographic / Esri",
                show=False,
            ).add_to(m)

            for layer_cfg in active_wms_layers_for_province(
                official_gis_layers,
                "Neuquen"
            ):
                try:
                    folium.raster_layers.WmsTileLayer(
                        url=layer_cfg["url"],
                        layers=layer_cfg["technical_layer"],
                        name=f"Neuquen - {layer_cfg['name']}",
                        fmt="image/png",
                        transparent=True,
                        version="1.1.1",
                        overlay=True,
                        control=True,
                        show=layer_cfg["show"],
                    ).add_to(m)
                except Exception:
                    pass

            fg = folium.FeatureGroup(name="UEIP scored areas by operator", show=True, control=True)
            for idx, row in scored.iterrows():
                try:
                    lat = float(row["lat"])
                    lon = float(row["lon"])
                    score = float(row.get("rig_demand_score", 50))
                except Exception:
                    continue

                op = str(row.get("operator", "Unknown"))
                area = str(row.get("area", ""))
                basin = str(row.get("detected_basin", row.get("basin", "")))
                province = str(row.get("province", ""))
                color = color_for_operator(op)
                r = score_radius(score)
                tooltip = f"{area} | {op} | Drill Score {int(round(score))}"
                popup = f"""
                <b>{area}</b><br>
                Operator: {op}<br>
                Drill Score: {int(round(score))}<br>
                Priority: {priority(score)}<br>
                Basin: {basin}<br>
                Province: {province}<br>
                """

                folium.Marker(
                    [lat, lon],
                    tooltip=tooltip,
                    popup=folium.Popup(popup, max_width=380),
                    icon=folium.DivIcon(
                        html=score_icon(score, color),
                        icon_size=(r * 2, r * 2),
                        icon_anchor=(r, r),
                    ),
                ).add_to(fg)

            fg.add_to(m)
            folium.LayerControl(collapsed=False, position="topright").add_to(m)
            Fullscreen(position="topright").add_to(m)
            MiniMap(toggle_display=True, position="bottomleft").add_to(m)
            MeasureControl(position="topleft").add_to(m)
            MousePosition(position="bottomright", separator=" | ", prefix="Lat/Lon:", num_digits=5).add_to(m)

            map_state = st_folium(
                m,
                width=None,
                height=760,
                returned_objects=["last_object_clicked_tooltip"],
                key="ueip_main_map_contextual",
            )

            if map_state and map_state.get("last_object_clicked_tooltip"):
                selected_label = map_state["last_object_clicked_tooltip"]
                parts = [p.strip() for p in selected_label.split("|")]
                if len(parts) >= 2 and not scored.empty:
                    area_match, op_match = parts[0], parts[1]
                    matches = scored[
                        (scored["area"].astype(str) == area_match)
                        & (scored["operator"].astype(str) == op_match)
                    ]
                    if not matches.empty:
                        selected_row = matches.iloc[0].to_dict()
                        st.session_state["selected_map_row"] = selected_row
            elif "selected_map_row" in st.session_state:
                selected_row = st.session_state["selected_map_row"]

        if selected_row:
            selected_label = (
                f"Argentina › {selected_row.get('detected_basin', selected_row.get('basin',''))} › "
                f"{selected_row.get('area','')} › {selected_row.get('operator','')} › Score {int(round(float(selected_row.get('rig_demand_score',50))))}"
            )

        st.markdown(f'<div class="uc-footer">{selected_label}</div>', unsafe_allow_html=True)

    with right_col:
        if selected_row:
            selected_basin = selected_row.get("detected_basin", selected_row.get("basin", "Argentina"))
            selected_area = selected_row.get("area", "")
            selected_operator = selected_row.get("operator", "")
            selected_score = float(selected_row.get("rig_demand_score", 50))
            selected_province = selected_row.get("province", "")
        else:
            selected_basin = "Neuquén Basin"
            selected_area = "Vaca Muerta"
            selected_operator = "Select an area"
            selected_score = 0
            selected_province = "Neuquén"

        context = layer_context_for_basin(selected_basin)
        official_layers_html = ""

        for label, active in context["official"]:
            box_class = "layer-box" if active else "layer-box off"
            mark = "✓" if active else ""
            official_layers_html += f'<div class="layer-row"><div class="{box_class}">{mark}</div>{label}</div>'

        services_html = "".join([
            f'<span class="detail-pill">{tag}</span>'
            for tag in multi_service_tags(selected_score, selected_basin)
        ])

        contractor_info = contractor_context_for_operator(selected_operator)

        if contractor_info:
            contractor_html = f"""
              <div class="detail-row"><span>Current Contractor</span><span>{contractor_info.get("current_contractor", "-")}</span></div>
              <div class="detail-row"><span>Contract Type</span><span>{contractor_info.get("contract_type", "-")}</span></div>
              <div class="detail-row"><span>Rig Type</span><span>{contractor_info.get("rig_type", "-")}</span></div>
              <div class="detail-row"><span>Rig Count</span><span>{contractor_info.get("rig_count", "-")}</span></div>
            """
        else:
            contractor_html = """
              <div class="detail-row"><span>Current Contractor</span><span>To verify</span></div>
              <div class="detail-row"><span>Contract Type</span><span>Unknown</span></div>
              <div class="detail-row"><span>Rig Type</span><span>Unknown</span></div>
              <div class="detail-row"><span>Rig Count</span><span>-</span></div>
            """

        fleet_html = contractor_fleet_html(contractor_info, rig_fleet)
        rig_forecast_text = forecast_rigs(selected_score) if selected_score else "-"

        rig_gap_block = rig_gap_html(
            rig_forecast_text,
            contractor_info
        )
        observed_activity_block = observed_activity_html(
        selected_area,
        selected_operator,
        observed_activity
)
        tender_probability_block = tender_probability_html(
        selected_area,
        selected_operator,
        tender_probability
)
        forecast_intelligence_block = forecast_intelligence_html(
        selected_area,
        selected_operator,
        forecast_intelligence
)
        contract_intelligence_block = contract_intelligence_html(
        selected_area,
        selected_operator,
        contract_intelligence
)
        capital_program_block = capital_program_html(
        selected_area,
        selected_operator,
        capital_program
)
        commercial_action_block = commercial_action_html(
        selected_area,
        selected_operator,
        rig_expansion,
        rig_commitments,
        contract_intelligence,
        capital_program
)
        rig_expansion_block = rig_expansion_html(
        selected_area,
        selected_operator,
        rig_expansion
)

        rig_commitment_block = rig_commitment_html(
        selected_area,
        selected_operator,
        rig_commitments
) 
       
        st.html(f"""
        <div class="right-panel">
          <div class="panel-title">MAP LAYERS</div>

          <div class="layer-group-title">CURRENT CONTEXT</div>
          <div class="layer-select">Argentina</div>
          <div class="layer-select">{context["zone"]}</div>

          <div class="detail-card">
            <b>{selected_area}</b>

            <div class="detail-row"><span>Operator</span><span>{selected_operator}</span></div>
            <div class="detail-row"><span>Province</span><span>{selected_province}</span></div>
            <div class="detail-row"><span>Basin</span><span>{selected_basin}</span></div>
            <div class="detail-row"><span>Rig forecast</span><span>{forecast_rigs(selected_score) if selected_score else "-"}</span></div>

            <div class="alert-banner">
            Intelligence available: Contract / CAPEX / Rig Commitment / Services
            </div>

            <div style="margin-top:9px;"><b>Commercial Summary</b></div>
            {commercial_action_block}

            <div style="margin-top:9px;"><b>Rig Expansion Intelligence</b></div>
            {rig_expansion_block}

            <div style="margin-top:9px;"><b>Rig Commitment Intelligence</b></div>
            {rig_commitment_block}

            <div style="margin-top:9px;"><b>Contract Intelligence</b></div>
            {contract_intelligence_block}

            <div style="margin-top:7px;"><b>Available Services</b><br>{services_html}</div>

          <div class="layer-group-title">MAP CONTROLS</div>
          <div class="layer-row">
          Use the real layer control inside the map to toggle official GIS layers.
        </div>
        """)


with tabs[2]:
    st.markdown(
        '<div class="uc-score-card"><b>Score Comp.</b><table><tr><th>Component</th><th>Weight</th></tr><tr><td>Permits / EIA</td><td>40%</td></tr><tr><td>Investor / CAPEX Signal</td><td>30%</td></tr><tr><td>Activity Intensity</td><td>20%</td></tr><tr><td>Operator Tier / Core Relevance</td><td>10%</td></tr></table></div>',
        unsafe_allow_html=True,
    )
    st.header("Operator Intelligence")
    if not operator_forecast.empty:
        st.dataframe(clean_table(operator_forecast), use_container_width=True)
    if not operator_signals.empty:
        st.subheader("Underlying Signals")
        st.dataframe(clean_table(operator_signals), use_container_width=True)


with tabs[3]:

    st.header("Rig Opportunity Ranking")

    st.caption(
        "Areas ranked by estimated rig demand, contractor coverage and commercial opportunity."
    )

    if not opportunity_ranking.empty:

        st.dataframe(
            opportunity_ranking,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info("No opportunity ranking available.")
        st.subheader("Tender Probability Ranking")

        st.dataframe(
        tender_probability,
        use_container_width=True
)
        st.subheader("Forecast Intelligence Ranking")

        st.dataframe(
        forecast_intelligence,
        use_container_width=True
)
        st.subheader("Contract Intelligence Ranking")

        st.dataframe(
        contract_intelligence,
        use_container_width=True
)
with tabs[4]:
    st.header("Top Commercial Targets")

    commercial_targets = enrich_opportunity_ranking(rig_strategy)

    st.dataframe(
        commercial_targets,
        use_container_width=True
    )
with tabs[5]:

    st.header("Area Intelligence")

    if not areas.empty:

        st.dataframe(
            clean_table(areas),
            use_container_width=True
        )
with tabs[6]:
    st.header("Permit Pipeline")
    if not permits_pipeline.empty:
        st.dataframe(clean_table(permits_pipeline), use_container_width=True)
    if not changes_log.empty:
        st.subheader("Changes Log")
        st.dataframe(clean_table(changes_log), use_container_width=True)


with tabs[7]:
    st.header("Rig Coverage / Operator Rig Strategy")

    if not rig_strategy.empty:
        st.dataframe(clean_table(rig_strategy), use_container_width=True)

    if not providers.empty:
        st.subheader("Rig and Service Providers")
        st.dataframe(clean_table(providers), use_container_width=True)

    if not contractor_intelligence.empty:
        st.subheader("Contractor Intelligence")
        st.dataframe(contractor_intelligence, use_container_width=True)

    if not rig_fleet.empty:
        st.subheader("Rig Fleet Registry")
        st.dataframe(rig_fleet, use_container_width=True)

with tabs[8]:
    st.header("Multi-Service Opportunity Layer")
    if not services.empty:
        st.subheader("Service Master")
        st.dataframe(clean_table(services), use_container_width=True)
    if not service_rules.empty:
        st.subheader("Service Opportunity Rules")
        st.dataframe(clean_table(service_rules), use_container_width=True)
    
with tabs[9]:

    st.header("Operational Activity Intelligence")

    st.caption(
        "Operational Activity Score combines drilling, frac, production, seismic and well-status signals."
    )

    st.subheader("Top Operational Activity Areas")

    st.dataframe(
        top_operational_activity(activity_scores),
        use_container_width=True
    )

    st.subheader("Activity Summary by Operator")

    st.dataframe(
        activity_summary_by_operator(activity_scores),
        use_container_width=True
    )

    st.subheader("Activity Summary by Basin")

    st.dataframe(
        activity_summary_by_basin(activity_scores),
        use_container_width=True
    )
    st.divider()

    st.subheader("Observed Activity Intelligence")

    st.caption(
    "Observed activity combines production, drilling and well-status signals."
)

    st.subheader("Top Areas by Observed Activity")

    st.dataframe(
    observed_activity_by_area(observed_activity),
    use_container_width=True
)

    st.subheader("Observed Activity by Operator")

    st.dataframe(
    observed_activity_by_operator(observed_activity),
    use_container_width=True
)


with tabs[10]:
    st.header("Score")
    st.markdown(
        '<div class="uc-score-card"><h3>Rig Demand Score</h3><table><tr><th>Score Component</th><th>Weight</th></tr><tr><td>Permits / EIA</td><td>40%</td></tr><tr><td>Investor / CAPEX Signal</td><td>30%</td></tr><tr><td>Activity Intensity</td><td>20%</td></tr><tr><td>Operator Tier / Core Relevance</td><td>10%</td></tr></table><p>The score estimates the probability that an operator will require drilling rigs or associated services within the next 6–18 months.</p></div>',
        unsafe_allow_html=True,
    )


with tabs[11]:

    st.header("Official Energy Data Registry")

    st.subheader("Official GIS Layer Status")

    st.dataframe(
        gis_source_status(official_gis_layers),
        use_container_width=True
    )

    st.subheader("Pending GIS Sources")

    st.dataframe(
        pending_gis_sources(official_gis_layers),
        use_container_width=True
    )

    st.subheader("Full Official GIS Layer Registry")

    st.dataframe(
        official_gis_layers,
        use_container_width=True
    )

    st.caption(
        "Official datasets connected to the ULTRACORE intelligence platform."
    )
    st.subheader("Energy Dataset Status")

    st.dataframe(
    dataset_status_summary(energy_datasets),
    use_container_width=True
)

    st.subheader("Rig Demand Score v2 Inputs")

    st.dataframe(
    rig_score_weight_table(energy_datasets),
    use_container_width=True
)

    st.subheader("Critical Dataset Backlog")

    st.dataframe(
    critical_dataset_backlog(energy_datasets),
    use_container_width=True
)
    st.subheader("Source Summary")

    st.dataframe(
        source_summary_by_module(official_sources),
        use_container_width=True
    )

    st.subheader("Registered Sources")

    st.dataframe(
        official_sources,
        use_container_width=True
    )
with tabs[12]:
    st.header("Capital Program Intelligence")

    st.dataframe(
        capital_program,
        use_container_width=True
    )
with tabs[13]:

    st.header("Data Export")

    for filename, df in {
        "operator_forecast.csv": operator_forecast,
        "operator_signals.csv": operator_signals,
        "operator_area_forecast.csv": operator_area_forecast,
        "permits_pipeline_auto.csv": permits_pipeline,
        "area_master.csv": areas,
        "operator_rig_strategy.csv": rig_strategy,
        "service_master.csv": services,
    }.items():

        if not df.empty:

            st.download_button(
                filename,
                clean_table(df).to_csv(index=False).encode("utf-8"),
                file_name=filename,
                mime="text/csv",
            )

