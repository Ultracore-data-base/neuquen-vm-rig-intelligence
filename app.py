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


st.set_page_config(page_title='Ultracore Energy Intelligence Platform', page_icon='🛢️', layout='wide', initial_sidebar_state='collapsed')

DATA_DIR = Path('data')


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
    return df.drop(columns=[c for c in ['score_definition'] if c in df.columns])


def color_for_operator(operator):
    palette = {
        'YPF': '#1769E8', 'VISTA': '#21A64A', 'PAN AMERICAN': '#FF7A00',
        'PAE': '#FF7A00', 'PAMPA': '#9C27D3', 'PLUSPETROL': '#FFC400',
        'TECPETROL': '#00A9B8', 'SHELL': '#E53935', 'CGC': '#EC2F8C',
        'CHEVRON': '#2E63B8', 'TOTAL': '#7A7A7A', 'GEOPARK': '#21A64A',
    }
    text = str(operator).upper()
    for key, value in palette.items():
        if key in text:
            return value
    fallback = ['#1769E8', '#21A64A', '#FF7A00', '#9C27D3', '#FFC400', '#00A9B8', '#E53935', '#EC2F8C', '#2E63B8']
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
        return 'Unknown'
    if score >= 85:
        return 'Strategic'
    if score >= 70:
        return 'High'
    if score >= 50:
        return 'Medium'
    return 'Low'


def score_icon(score, color):
    r = score_radius(score)
    d = r * 2
    fs = max(11, int(r * 0.68))
    return f'''
    <div style="width:{d}px;height:{d}px;border-radius:50%;background:{color};border:2px solid #fff;
    box-shadow:0 5px 12px rgba(0,0,0,.36),0 0 0 1px rgba(0,0,0,.16);
    display:flex;align-items:center;justify-content:center;color:white;font-weight:900;font-size:{fs}px;
    font-family:Arial, sans-serif;text-shadow:0 2px 4px rgba(0,0,0,.45);">{int(round(float(score)))}</div>
    '''


def build_scored_points(area_master, area_forecast, op_forecast):
    if not area_forecast.empty and {'lat', 'lon'}.issubset(area_forecast.columns):
        df = area_forecast.copy()
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        if 'rig_demand_score' not in df.columns:
            df['rig_demand_score'] = 50
        df['rig_demand_score'] = pd.to_numeric(df['rig_demand_score'], errors='coerce').fillna(50)
        if 'operator' not in df.columns:
            df['operator'] = 'Unknown'
        if 'area' not in df.columns:
            df['area'] = ''
        df = df.dropna(subset=['lat', 'lon'])
        if len(df) >= 4:
            return df

    if area_master.empty or not {'lat', 'lon'}.issubset(area_master.columns):
        return pd.DataFrame()

    df = area_master.copy()
    df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
    df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
    df = df.dropna(subset=['lat', 'lon'])

    if not op_forecast.empty and {'operator', 'rig_demand_score'}.issubset(op_forecast.columns):
        f = clean_table(op_forecast).copy()
        f['rig_demand_score'] = pd.to_numeric(f['rig_demand_score'], errors='coerce')
        df = df.merge(f[['operator', 'rig_demand_score']].drop_duplicates('operator'), on='operator', how='left')

    if 'rig_demand_score' not in df.columns:
        df['rig_demand_score'] = pd.to_numeric(df.get('confidence', 50), errors='coerce').fillna(50)
    else:
        df['rig_demand_score'] = df['rig_demand_score'].fillna(pd.to_numeric(df.get('confidence', 50), errors='coerce').fillna(50))

    df = df.reset_index(drop=True)
    for i in range(len(df)):
        df.loc[i, 'lat'] = df.loc[i, 'lat'] + ((i % 5) - 2) * 0.012
        df.loc[i, 'lon'] = df.loc[i, 'lon'] + ((i % 7) - 3) * 0.012
    return df


operator_forecast = load_csv('operator_forecast.csv')
operator_signals = load_csv('operator_signals.csv')
operator_area_forecast = load_csv('operator_area_forecast.csv')
permits_pipeline = load_csv('permits_pipeline_auto.csv')
changes_log = load_csv('changes_log.csv')
countries = load_csv('countries.csv')
basins = load_csv('basin_master.csv')
operators = load_csv('operator_master.csv')
areas = load_csv('area_master.csv')
services = load_csv('service_master.csv')
providers = load_csv('rig_provider_master.csv')
rig_strategy = load_csv('operator_rig_strategy.csv')
service_rules = load_csv('service_opportunity_rules.csv')
gis_layers = load_csv('gis_layer_registry.csv')

scored = build_scored_points(areas, operator_area_forecast, operator_forecast)

st.markdown('''
<style>
html, body, [data-testid="stAppViewContainer"] {background:#06111d;}
.block-container {padding:0 !important; max-width:100% !important;}
header[data-testid="stHeader"] {height:0px !important; background:transparent !important;}
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {display:none !important;}
div[data-testid="stVerticalBlock"] {gap:0 !important;}
div[data-testid="stHorizontalBlock"] {gap:0 !important;}
div[data-testid="column"] {padding:0 !important;}
div[data-testid="stTabs"]{background:#061321 !important;}
div[data-testid="stTabs"] > div:first-child{
  padding-left:0.25rem !important; border-bottom:1px solid rgba(255,255,255,.1) !important;
  min-height:44px !important; background:#061321 !important; position:relative !important; z-index:1000 !important;
}
div[data-testid="stTabs"] button{color:#dbe7f2 !important;font-weight:800 !important;opacity:1 !important;}
div[data-testid="stTabs"] button p{color:#dbe7f2 !important;opacity:1 !important;}
div[data-testid="stTabs"] button[aria-selected="true"]{color:white !important;border-bottom:3px solid #168BFF !important;}
.uc-top{display:none !important;height:0 !important;padding:0 !important;margin:0 !important;}
.panel-shell{background:linear-gradient(180deg,#092034,#061321);color:white;height:760px;overflow-y:auto;padding:13px 12px;border-right:1px solid rgba(255,255,255,.08);border-left:1px solid rgba(255,255,255,.05);}
.right-panel{background:linear-gradient(180deg,#f8fafc,#eef3f7);color:#122033;height:760px;overflow-y:auto;padding:13px 12px;border-left:1px solid rgba(0,0,0,.10);}
.panel-title{font-size:14px;font-weight:900;letter-spacing:.5px;margin-bottom:8px;}
.panel-subtitle{font-size:12.5px;color:#b6c6d6;margin-bottom:8px;}
.right-panel .panel-subtitle{color:#526173;}
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
iframe {display:block !important;}
.uc-footer{height:32px;line-height:32px;background:#061321;color:#fff;padding:0 14px;font-size:13px;font-weight:750;border-top:1px solid rgba(255,255,255,.08);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.uc-score-card{background:white;color:#172638;border-radius:14px;padding:18px 20px;margin:14px 18px;box-shadow:0 8px 22px rgba(0,0,0,.18);}
.uc-score-card table{width:100%;border-collapse:collapse;}
.uc-score-card th,.uc-score-card td{padding:9px;border-bottom:1px solid #e6ebf0;}
.uc-score-card td:last-child,.uc-score-card th:last-child{text-align:right;font-weight:900;}
section.main > div {padding-bottom:0 !important;}
</style>
''', unsafe_allow_html=True)

tabs = st.tabs(['Executive Summary','Immersive GIS Map','Operator Intelligence','Area Intelligence','Permit Pipeline','Rig Coverage','Multi-Service','Score','Data Export'])

with tabs[0]:
    st.markdown('<div style="padding:22px;color:white;">', unsafe_allow_html=True)
    st.header('Ultracore Energy Intelligence Platform')
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Countries', len(countries))
    c2.metric('Basins', len(basins))
    c3.metric('Areas / blocks', len(areas))
    c4.metric('Operators', len(operators))
    if not operator_forecast.empty:
        st.subheader('Top Operator Rig Demand Ranking')
        st.dataframe(clean_table(operator_forecast), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tabs[1]:
    left_col, map_col, right_col = st.columns([1.05, 4.65, 1.05], gap='small')

    with left_col:
        op_rows = ''
        if not scored.empty:
            op_scores = scored.groupby('operator', dropna=False)['rig_demand_score'].max().reset_index().sort_values('rig_demand_score', ascending=False)
            for _, row in op_scores.head(18).iterrows():
                op = str(row['operator'])
                score = float(row['rig_demand_score'])
                color = color_for_operator(op)
                op_rows += f'''
                <div class="op-row"><div class="op-left"><div class="op-check" style="background:{color};">✓</div>
                <div><div class="op-name">{op}</div><div class="op-sub">Score</div></div></div>
                <div class="op-score" style="background:{color};">{int(round(score))}</div></div>'''
        else:
            op_rows = "<div style='color:#b6c6d6;font-size:13px;'>No scored areas yet.</div>"

        st.markdown(f'''
        <div class="panel-shell"><div class="panel-title">OPERATOR LEGEND ⓘ</div>
        <div class="panel-subtitle">Show / Hide all operators</div>{op_rows}</div>
        ''', unsafe_allow_html=True)

    with map_col:
        selected_label = 'Argentina › Neuquén Basin › Vaca Muerta'

        if folium is None or st_folium is None:
            st.error('folium / streamlit-folium missing')
        else:
            center = [-38.55, -68.75]
            zoom = 8
            if not scored.empty and {'lat', 'lon'}.issubset(scored.columns):
                use = scored
                if 'province' in scored.columns:
                    neuq = scored[scored['province'].astype(str).str.contains('Neuquen|Neuquén', case=False, na=False)]
                    if not neuq.empty:
                        use = neuq
                lat_series = pd.to_numeric(use['lat'], errors='coerce').dropna()
                lon_series = pd.to_numeric(use['lon'], errors='coerce').dropna()
                if not lat_series.empty and not lon_series.empty:
                    center = [float(lat_series.median()), float(lon_series.median())]

            m = folium.Map(location=center, zoom_start=zoom, tiles=None, control_scale=True, prefer_canvas=True)
            folium.TileLayer('OpenStreetMap', name='OpenStreetMap / roads', show=True).add_to(m)
            folium.TileLayer(tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='Satellite / Esri World Imagery', show=False).add_to(m)
            folium.TileLayer(tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='Topographic / Esri', show=False).add_to(m)

            neuquen_wms = 'https://hidrocarburos.energianeuquen.gob.ar/geoserver/wms'
            for layer, name, show in [
                ('Hidrocarburos:Areas', 'Neuquen - Areas / concessions', True),
                ('Hidrocarburos:Pozos_VM', 'Neuquen - Vaca Muerta wells', True),
                ('Hidrocarburos:Pozos', 'Neuquen - Wells', False),
                ('Hidrocarburos:Ductos', 'Neuquen - Ducts', False),
                ('Hidrocarburos:Instalaciones', 'Neuquen - Facilities', False),
                ('Hidrocarburos:Locaciones', 'Neuquen - Locations', False),
            ]:
                try:
                    folium.raster_layers.WmsTileLayer(url=neuquen_wms, layers=layer, name=name, fmt='image/png', transparent=True, version='1.1.1', overlay=True, control=False, show=show).add_to(m)
                except Exception:
                    pass

            fg = folium.FeatureGroup(name='UEIP scored areas by operator', show=True, control=False)
            for _, row in scored.iterrows():
                try:
                    lat = float(row['lat'])
                    lon = float(row['lon'])
                    score = float(row.get('rig_demand_score', 50))
                except Exception:
                    continue

                op = str(row.get('operator', 'Unknown'))
                area = str(row.get('area', ''))
                basin = str(row.get('basin', ''))
                province = str(row.get('province', ''))
                color = color_for_operator(op)
                r = score_radius(score)
                tooltip = f'{area} | {op} | Drill Score {int(round(score))}'
                popup = f'<b>{area}</b><br>Operator: {op}<br>Drill Score: {int(round(score))}<br>Priority: {priority(score)}<br>Basin: {basin}<br>Province: {province}<br>'

                folium.Marker([lat, lon], tooltip=tooltip, popup=folium.Popup(popup, max_width=380), icon=folium.DivIcon(html=score_icon(score, color), icon_size=(r * 2, r * 2), icon_anchor=(r, r))).add_to(fg)

            fg.add_to(m)
            Fullscreen(position='topright').add_to(m)
            MiniMap(toggle_display=True, position='bottomleft').add_to(m)
            MeasureControl(position='topleft').add_to(m)
            MousePosition(position='bottomright', separator=' | ', prefix='Lat/Lon:', num_digits=5).add_to(m)

            map_state = st_folium(m, width=None, height=760, returned_objects=['last_object_clicked_tooltip'], key='ueip_main_map_with_right_panel')
            if map_state and map_state.get('last_object_clicked_tooltip'):
                selected_label = map_state['last_object_clicked_tooltip']

        st.markdown(f'<div class="uc-footer">{selected_label}</div>', unsafe_allow_html=True)

    with right_col:
        st.markdown('''
        <div class="right-panel">
          <div class="panel-title">MAP LAYERS</div>
          <div class="layer-group-title">ZONE FILTER</div>
          <div class="layer-select">Argentina</div>
          <div class="layer-select">Neuquén / Cuenca Neuquina</div>
          <div class="layer-group-title">BASE MAP</div>
          <div class="layer-row"><div class="layer-box">✓</div>OpenStreetMap / roads</div>
          <div class="layer-row"><div class="layer-box off"></div>Satellite / Esri</div>
          <div class="layer-row"><div class="layer-box off"></div>Topographic / Esri</div>
          <div class="layer-group-title">OFFICIAL GIS LAYERS</div>
          <div class="layer-row"><div class="layer-box">✓</div>Areas / concessions</div>
          <div class="layer-row"><div class="layer-box">✓</div>Vaca Muerta wells</div>
          <div class="layer-row"><div class="layer-box off"></div>Wells</div>
          <div class="layer-row"><div class="layer-box off"></div>Ducts</div>
          <div class="layer-row"><div class="layer-box off"></div>Facilities</div>
          <div class="layer-row"><div class="layer-box off"></div>Locations</div>
          <div class="layer-group-title">ULTRACORE LAYERS</div>
          <div class="layer-row"><div class="layer-box">✓</div>Scored areas by operator</div>
          <div class="layer-row"><div class="layer-box off"></div>Rig coverage</div>
          <div class="layer-row"><div class="layer-box off"></div>Multi-service opportunity</div>
        </div>
        ''', unsafe_allow_html=True)

with tabs[2]:
    st.markdown('<div class="uc-score-card"><b>Score Comp.</b><table><tr><th>Component</th><th>Weight</th></tr><tr><td>Permits / EIA</td><td>40%</td></tr><tr><td>Investor / CAPEX Signal</td><td>30%</td></tr><tr><td>Activity Intensity</td><td>20%</td></tr><tr><td>Operator Tier / Core Relevance</td><td>10%</td></tr></table></div>', unsafe_allow_html=True)
    st.header('Operator Intelligence')
    if not operator_forecast.empty:
        st.dataframe(clean_table(operator_forecast), use_container_width=True)
    if not operator_signals.empty:
        st.subheader('Underlying Signals')
        st.dataframe(clean_table(operator_signals), use_container_width=True)

with tabs[3]:
    st.header('Area Intelligence')
    if not operator_area_forecast.empty:
        st.dataframe(clean_table(operator_area_forecast), use_container_width=True)
    if not areas.empty:
        st.subheader('National Area Master')
        st.dataframe(clean_table(areas), use_container_width=True)

with tabs[4]:
    st.header('Permit Pipeline')
    if not permits_pipeline.empty:
        st.dataframe(clean_table(permits_pipeline), use_container_width=True)
    if not changes_log.empty:
        st.subheader('Changes Log')
        st.dataframe(clean_table(changes_log), use_container_width=True)

with tabs[5]:
    st.header('Rig Coverage / Operator Rig Strategy')
    if not rig_strategy.empty:
        st.dataframe(clean_table(rig_strategy), use_container_width=True)
    if not providers.empty:
        st.subheader('Rig and Service Providers')
        st.dataframe(clean_table(providers), use_container_width=True)

with tabs[6]:
    st.header('Multi-Service Opportunity Layer')
    if not services.empty:
        st.subheader('Service Master')
        st.dataframe(clean_table(services), use_container_width=True)
    if not service_rules.empty:
        st.subheader('Service Opportunity Rules')
        st.dataframe(clean_table(service_rules), use_container_width=True)

with tabs[7]:
    st.header('Score')
    st.markdown('<div class="uc-score-card"><h3>Rig Demand Score</h3><table><tr><th>Score Component</th><th>Weight</th></tr><tr><td>Permits / EIA</td><td>40%</td></tr><tr><td>Investor / CAPEX Signal</td><td>30%</td></tr><tr><td>Activity Intensity</td><td>20%</td></tr><tr><td>Operator Tier / Core Relevance</td><td>10%</td></tr></table><p>The score estimates the probability that an operator will require drilling rigs or associated services within the next 6–18 months.</p></div>', unsafe_allow_html=True)

with tabs[8]:
    st.header('Data Export')
    for filename, df in {
        'operator_forecast.csv': operator_forecast,
        'operator_signals.csv': operator_signals,
        'operator_area_forecast.csv': operator_area_forecast,
        'permits_pipeline_auto.csv': permits_pipeline,
        'area_master.csv': areas,
        'operator_rig_strategy.csv': rig_strategy,
        'service_master.csv': services,
    }.items():
        if not df.empty:
            st.download_button(filename, clean_table(df).to_csv(index=False).encode('utf-8'), file_name=filename, mime='text/csv')


            


