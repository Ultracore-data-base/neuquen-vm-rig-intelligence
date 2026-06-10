import re
import json
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

DATA_DIR = Path('data')
DATA_DIR.mkdir(exist_ok=True)

OUT_SIGNALS = DATA_DIR / 'operator_signals.csv'
OUT_FORECAST = DATA_DIR / 'operator_forecast.csv'
OUT_AREA_FORECAST = DATA_DIR / 'operator_area_forecast.csv'
OUT_STATE = DATA_DIR / 'investor_last_run.json'
PERMITS_FILE = DATA_DIR / 'permits_pipeline_auto.csv'

TIMEOUT = 12
HEADERS = {'User-Agent': 'Mozilla/5.0 neuquen-rig-intelligence/2.0'}

OPERATORS = {
    'YPF': ['https://inversores.ypf.com/', 'https://www.ypf.com/'],
    'VISTA': ['https://www.vistaenergy.com/'],
    'TECPETROL': ['https://www.tecpetrol.com/', 'https://www.techint.com/'],
    'PAE': ['https://www.pan-energy.com/', 'https://www.pan-energy.com/inversores/'],
    'PLUSPETROL': ['https://www.pluspetrol.net/'],
    'SHELL': ['https://www.shell.com.ar/', 'https://www.shell.com/investors.html'],
    'CHEVRON': ['https://www.chevron.com/investors'],
    'TOTALENERGIES': ['https://totalenergies.com/investors'],
    'PAMPA': ['https://www.pampaenergia.com/', 'https://ri.pampaenergia.com/'],
    'CGC': ['https://www.cgc.energy/'],
    'CAPEX': ['https://www.capex.com.ar/'],
    'PHOENIX': ['https://www.phoenixglobalresources.com/'],
    'EXXONMOBIL': ['https://corporate.exxonmobil.com/', 'https://investor.exxonmobil.com/'],
    'EQUINOR': ['https://www.equinor.com/'],
    'PETRONAS': ['https://www.petronas.com/'],
    'GEOPARK': ['https://www.geo-park.com/'],
    'HARBOUR': ['https://www.harbourenergy.com/'],
    'OILSTONE': ['https://www.oilstone.com.ar/'],
    'ACONCAGUA': ['https://www.aconcaguaenergia.com/'],
    'PRESIDENT': ['https://www.presidentenergyplc.com/'],
    'MEDANITO': ['https://www.medanito.com.ar/'],
    'MADALENA': ['https://www.madalenaenergy.com/'],
    'KILWER': ['https://www.kilwer.com.ar/'],
    'SELVA_MARIA': [],
}

ALIASES = {
    'YPF': ['YPF', 'YACIMIENTOS PETROLIFEROS FISCALES'],
    'VISTA': ['VISTA', 'VISTA ENERGY', 'VISTA ENERGY ARGENTINA'],
    'TECPETROL': ['TECPETROL', 'TECHINT'],
    'PAE': ['PAE', 'PAN AMERICAN ENERGY', 'PAN AMERICAN ENERGY SL'],
    'PLUSPETROL': ['PLUSPETROL', 'PLUSPETROL S.A.', 'PLUSPETROL CUENCA NEUQUINA'],
    'SHELL': ['SHELL', 'SHELL ARGENTINA'],
    'CHEVRON': ['CHEVRON', 'CHEVRON ARGENTINA'],
    'TOTALENERGIES': ['TOTAL', 'TOTAL AUSTRAL', 'TOTALENERGIES', 'TOTAL ENERGIES'],
    'PAMPA': ['PAMPA', 'PAMPA ENERGIA', 'PAMPA ENERGÍA'],
    'CGC': ['CGC', 'COMPAÑIA GENERAL DE COMBUSTIBLES', 'COMPAÑÍA GENERAL DE COMBUSTIBLES'],
    'CAPEX': ['CAPEX', 'CAPSA'],
    'PHOENIX': ['PHOENIX', 'PHOENIX GLOBAL', 'PHOENIX GLOBAL RESOURCES', 'PGR'],
    'EXXONMOBIL': ['EXXON', 'EXXONMOBIL', 'ESSO'],
    'EQUINOR': ['EQUINOR'],
    'PETRONAS': ['PETRONAS'],
    'GEOPARK': ['GEOPARK', 'GEO PARK'],
    'HARBOUR': ['HARBOUR', 'HARBOUR ENERGY', 'WINTERSHALL', 'WINTERSHALL DEA'],
    'OILSTONE': ['OILSTONE', 'OILSTONE ENERGIA', 'OILSTONE ENERGÍA'],
    'ACONCAGUA': ['ACONCAGUA', 'ACONCAGUA ENERGIA', 'ACONCAGUA ENERGÍA'],
    'PRESIDENT': ['PRESIDENT', 'PRESIDENT PETROLEUM'],
    'MEDANITO': ['MEDANITO'],
    'MADALENA': ['MADALENA', 'MADALENA ENERGY'],
    'KILWER': ['KILWER'],
    'SELVA_MARIA': ['SELVA MARIA', 'SELVA MARÍA', 'SELVA MARIA OIL'],
}

KEYWORDS = {
    'drilling': 35, 'perforación': 35, 'perforacion': 35,
    'pozos': 30, 'wells': 30, 'rig': 30, 'equipos de perforación': 35,
    'capex': 25, 'investment': 20, 'inversión': 20, 'inversion': 20,
    'vaca muerta': 30, 'neuquen': 15, 'neuquén': 15, 'shale': 20,
    'development plan': 25, 'plan de desarrollo': 25, 'pad': 25,
    'workover': 15, 'pulling': 10,
    'frac': 15, 'fracking': 15, 'efrac': 15, 'e-frac': 15, 'fractura': 15,
    'venting': 15, 'venteos': 15, 'emissions': 10, 'emisiones': 10,
    'guidance': 20, 'production growth': 15, 'crecimiento producción': 15,
}

CORE_AREAS = {
    'LOMA CAMPANA','LA AMARGA CHICA','BANDURRIA SUR','BAJADA DEL PALO','AGUA DEL CAJON',
    'FORTIN DE PIEDRA','LOS TOLDOS','COIRON AMARGO','SIERRAS BLANCAS','CRUZ DE LORENA',
    'LINDERO ATRAVESADO','ENTRE LOMAS','NEUQUEN DEL MEDIO','EL OREJANO','BAJO DEL CHOIQUE'
}

TOP_TIER = {'YPF','VISTA','TECPETROL','PAE','PLUSPETROL','SHELL','CHEVRON','TOTALENERGIES','PAMPA','CGC'}

AREA_COORDS = {
    'LOMA CAMPANA': (-38.21, -68.86), 'LA AMARGA CHICA': (-38.38, -68.75),
    'BANDURRIA SUR': (-38.34, -68.62), 'BAJADA DEL PALO': (-38.05, -68.72),
    'AGUA DEL CAJON': (-38.83, -68.41), 'FORTIN DE PIEDRA': (-38.60, -68.73),
    'LOS TOLDOS': (-38.45, -68.95), 'COIRON AMARGO': (-38.12, -69.20),
    'SIERRAS BLANCAS': (-38.25, -68.68), 'CRUZ DE LORENA': (-38.22, -68.54),
    'LINDERO ATRAVESADO': (-38.55, -68.50), 'ENTRE LOMAS': (-37.90, -68.45),
    'NEUQUEN DEL MEDIO': (-38.93, -68.77), 'EL OREJANO': (-38.30, -68.63),
}

def log(msg):
    print(f'[{datetime.now(timezone.utc).isoformat()}] {msg}', flush=True)

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code >= 400:
            return None
        return r.text
    except Exception as e:
        log(f'WARN fetch failed {url}: {e}')
        return None

def extract_links(base_url, html):
    soup = BeautifulSoup(html, 'html.parser')
    candidates = []
    for a in soup.find_all('a', href=True):
        text = ' '.join(a.get_text(' ', strip=True).split())
        href = urljoin(base_url, a['href'])
        hay = f'{text} {href}'.lower()
        if any(k in hay for k in ['investor','inversor','presentation','presentacion','results','annual','capex','sustainability','ambiente','pdf','operaciones','vaca','neuquen']):
            candidates.append((text or href, href))
    return candidates[:35]

def score_text(operator, text):
    t = (text or '').lower()
    score = 0
    hits = []
    for kw, pts in KEYWORDS.items():
        if kw in t:
            score += pts
            hits.append(kw)
    if operator in TOP_TIER:
        score += 15
    return min(score, 100), sorted(set(hits))

def classify_opportunity(hits):
    h = set(hits)
    opp = []
    if {'drilling','perforación','perforacion','pozos','wells','rig','pad','equipos de perforación'} & h:
        opp.append('Drilling rigs')
    if {'workover','pulling'} & h:
        opp.append('Workover')
    if {'frac','fracking','efrac','e-frac','fractura'} & h:
        opp.append('E-frac / stimulation')
    if {'venting','venteos','emissions','emisiones'} & h:
        opp.append('Venting / emissions')
    if not opp:
        opp.append('Strategic monitoring')
    return '; '.join(opp)

def normalize_operator(text):
    hay = (text or '').upper()
    for op, aliases in ALIASES.items():
        for alias in aliases:
            if alias.upper() in hay:
                return op
    return None

def extract_area(text):
    hay = (text or '').upper()
    for area in CORE_AREAS:
        if area in hay:
            return area
    return None

def read_permit_signals():
    if not PERMITS_FILE.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(PERMITS_FILE)
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return pd.DataFrame()
    rows = []
    for _, r in df.iterrows():
        joined = ' '.join(str(v) for v in r.values if pd.notna(v))
        op = normalize_operator(joined)
        area = extract_area(joined)
        if not op and 'operator' in df.columns:
            op = normalize_operator(str(r.get('operator','')))
        if not area and 'area' in df.columns:
            area = extract_area(str(r.get('area','')))
        if op:
            rows.append({
                'run_at': datetime.now(timezone.utc).isoformat(),
                'operator': op,
                'source_type': 'permit_environment_pipeline',
                'title': str(r.get('title', r.get('description', 'Permit / EIA signal')))[:250],
                'url': str(r.get('url', r.get('source_url', ''))),
                'area': area or str(r.get('area', '')).upper(),
                'keywords': 'permit;environment;pad;drilling',
                'score': 75 + (10 if area in CORE_AREAS else 0),
                'business_opportunity': 'Drilling rigs; Workover; Associated services',
            })
    return pd.DataFrame(rows)

def investor_signals():
    rows = []
    seen = set()
    for operator, urls in OPERATORS.items():
        for url in urls:
            log(f'Scanning {operator}: {url}')
            html = fetch(url)
            if not html:
                continue
            text = BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)[:70000]
            page_score, page_hits = score_text(operator, text)
            if page_score >= 25:
                key = (operator, url)
                if key not in seen:
                    rows.append({'run_at': datetime.now(timezone.utc).isoformat(),'operator': operator,'source_type': 'company_page','title': operator + ' source page','url': url,'area': extract_area(text) or '', 'keywords': ';'.join(page_hits),'score': page_score,'business_opportunity': classify_opportunity(page_hits)})
                    seen.add(key)
            for title, link in extract_links(url, html):
                s, hits = score_text(operator, f'{title} {link}')
                if s >= 30:
                    key = (operator, link)
                    if key not in seen:
                        rows.append({'run_at': datetime.now(timezone.utc).isoformat(),'operator': operator,'source_type': 'investor_or_public_link','title': title[:250],'url': link,'area': extract_area(title + ' ' + link) or '', 'keywords': ';'.join(hits),'score': s,'business_opportunity': classify_opportunity(hits)})
                        seen.add(key)
    return pd.DataFrame(rows)

def forecast_from_signals(signals):
    if signals.empty:
        return pd.DataFrame(columns=['operator','signals','permit_signals','investor_signals','max_score','avg_score','rig_demand_score','priority','score_definition'])
    signals['is_permit_signal'] = signals['source_type'].astype(str).str.contains('permit|environment', case=False, regex=True)
    forecast = (signals.groupby('operator', as_index=False)
        .agg(signals=('url','count'), permit_signals=('is_permit_signal','sum'), max_score=('score','max'), avg_score=('score','mean')))
    forecast['investor_signals'] = forecast['signals'] - forecast['permit_signals']
    def calc(r):
        # Rig Demand Score = 40% permit/EIA evidence + 30% investor/CAPEX evidence + 20% activity intensity + 10% operator tier/core relevance.
        permit_component = min(40, int(r['permit_signals']) * 12)
        investor_component = min(30, int(r['investor_signals']) * 8)
        intensity_component = min(20, int(r['max_score'] * 0.20))
        tier_component = 10 if r['operator'] in TOP_TIER else 5
        return min(100, permit_component + investor_component + intensity_component + tier_component)
    forecast['rig_demand_score'] = forecast.apply(calc, axis=1)
    forecast['priority'] = pd.cut(forecast['rig_demand_score'], bins=[-1,49,74,89,100], labels=['Low','Medium','High','Strategic'])
    forecast['score_definition'] = '40% permits/EIA + 30% investor/CAPEX signals + 20% activity intensity + 10% operator tier/core relevance'
    return forecast.sort_values('rig_demand_score', ascending=False)

def area_forecast(signals):
    if signals.empty or 'area' not in signals.columns:
        return pd.DataFrame(columns=['operator','area','signals','max_score','rig_demand_score','lat','lon'])
    df = signals.copy()
    df['area'] = df['area'].fillna('').astype(str).str.upper().str.strip()
    df = df[df['area'] != '']
    if df.empty:
        return pd.DataFrame(columns=['operator','area','signals','max_score','rig_demand_score','lat','lon'])
    out = df.groupby(['operator','area'], as_index=False).agg(signals=('url','count'), max_score=('score','max'))
    out['rig_demand_score'] = out.apply(lambda r: min(100, int(r['max_score'] * 0.7 + min(r['signals'],10) * 3)), axis=1)
    out['lat'] = out['area'].map(lambda a: AREA_COORDS.get(a, (None,None))[0])
    out['lon'] = out['area'].map(lambda a: AREA_COORDS.get(a, (None,None))[1])
    return out.sort_values('rig_demand_score', ascending=False)

def main():
    log('Investor crawler started')
    inv = investor_signals()
    permits = read_permit_signals()
    signals = pd.concat([inv, permits], ignore_index=True) if not permits.empty else inv
    cols = ['run_at','operator','source_type','title','url','area','keywords','score','business_opportunity']
    if signals.empty:
        signals = pd.DataFrame(columns=cols)
    else:
        for c in cols:
            if c not in signals.columns:
                signals[c] = ''
        signals = signals[cols]
    signals.to_csv(OUT_SIGNALS, index=False)
    forecast = forecast_from_signals(signals)
    forecast.to_csv(OUT_FORECAST, index=False)
    by_area = area_forecast(signals)
    by_area.to_csv(OUT_AREA_FORECAST, index=False)
    OUT_STATE.write_text(json.dumps({'run_at': datetime.now(timezone.utc).isoformat(), 'signals_total': int(len(signals)), 'operators_total': int(forecast['operator'].nunique()) if not forecast.empty else 0, 'areas_total': int(by_area['area'].nunique()) if not by_area.empty else 0}, indent=2), encoding='utf-8')
    log(json.dumps({'signals_total': int(len(signals)), 'top_operators': forecast.head(10).to_dict(orient='records'), 'top_areas': by_area.head(10).to_dict(orient='records')}, indent=2))

if __name__ == '__main__':
    main()

