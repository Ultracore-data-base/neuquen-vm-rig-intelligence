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
OUT_STATE = DATA_DIR / 'investor_last_run.json'

TIMEOUT = 12
HEADERS = {'User-Agent': 'Mozilla/5.0 neuquen-rig-intelligence/1.0'}

OPERATORS = {
    'YPF': ['https://inversores.ypf.com/', 'https://www.ypf.com/'],
    'VISTA': ['https://ir.vistaenergy.com/', 'https://www.vistaenergy.com/'],
    'TECPETROL': ['https://www.tecpetrol.com/', 'https://www.techint.com/'],
    'PAE': ['https://www.pan-energy.com/', 'https://www.pan-energy.com/inversores/'],
    'PLUSPETROL': ['https://www.pluspetrol.net/'],
    'SHELL': ['https://www.shell.com.ar/', 'https://www.shell.com/investors.html'],
    'CHEVRON': ['https://www.chevron.com/investors'],
    'TOTALENERGIES': ['https://totalenergies.com/investors'],
}

KEYWORDS = {
    'drilling': 35,
    'perforación': 35,
    'pozos': 30,
    'wells': 30,
    'rig': 30,
    'capex': 25,
    'investment': 20,
    'inversión': 20,
    'vaca muerta': 30,
    'shale': 20,
    'development plan': 25,
    'plan de desarrollo': 25,
    'pad': 25,
    'workover': 15,
    'frac': 15,
    'efrac': 15,
    'e-frac': 15,
    'venting': 15,
    'emissions': 10,
    'emisiones': 10,
    'guidance': 20,
    'production growth': 15,
}

TOP_TIER = {'YPF', 'VISTA', 'TECPETROL', 'PAE', 'PLUSPETROL', 'SHELL', 'CHEVRON'}


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
        if any(k in hay for k in ['investor', 'inversor', 'presentation', 'presentacion', 'results', 'annual', 'capex', 'sustainability', 'ambiente', 'pdf']):
            candidates.append((text or href, href))
    return candidates[:25]


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


def main():
    log('Investor crawler started')
    rows = []
    seen = set()
    for operator, urls in OPERATORS.items():
        for url in urls:
            log(f'Scanning {operator}: {url}')
            html = fetch(url)
            if not html:
                continue
            page_score, page_hits = score_text(operator, BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)[:50000])
            if page_score >= 25:
                key = (operator, url)
                if key not in seen:
                    rows.append({
                        'run_at': datetime.now(timezone.utc).isoformat(),
                        'operator': operator,
                        'source_type': 'company_page',
                        'title': operator + ' source page',
                        'url': url,
                        'keywords': ';'.join(page_hits),
                        'score': page_score,
                        'business_opportunity': classify_opportunity(page_hits),
                    })
                    seen.add(key)
            for title, link in extract_links(url, html):
                s, hits = score_text(operator, f'{title} {link}')
                if s >= 30:
                    key = (operator, link)
                    if key not in seen:
                        rows.append({
                            'run_at': datetime.now(timezone.utc).isoformat(),
                            'operator': operator,
                            'source_type': 'investor_or_public_link',
                            'title': title[:250],
                            'url': link,
                            'keywords': ';'.join(hits),
                            'score': s,
                            'business_opportunity': classify_opportunity(hits),
                        })
                        seen.add(key)
    signals = pd.DataFrame(rows)
    if signals.empty:
        signals = pd.DataFrame(columns=['run_at','operator','source_type','title','url','keywords','score','business_opportunity'])
    signals.to_csv(OUT_SIGNALS, index=False)

    if not signals.empty:
        forecast = (signals.groupby('operator', as_index=False)
            .agg(signals=('url','count'), max_score=('score','max'), avg_score=('score','mean')))
        forecast['rig_demand_score'] = forecast.apply(lambda r: min(100, int(r['max_score'] * 0.65 + r['avg_score'] * 0.25 + min(r['signals'], 10))), axis=1)
        forecast['priority'] = pd.cut(forecast['rig_demand_score'], bins=[-1,49,74,89,100], labels=['Low','Medium','High','Strategic'])
        forecast = forecast.sort_values('rig_demand_score', ascending=False)
    else:
        forecast = pd.DataFrame(columns=['operator','signals','max_score','avg_score','rig_demand_score','priority'])
    forecast.to_csv(OUT_FORECAST, index=False)
    OUT_STATE.write_text(json.dumps({'run_at': datetime.now(timezone.utc).isoformat(), 'signals_total': int(len(signals))}, indent=2), encoding='utf-8')
    log(json.dumps({'signals_total': int(len(signals)), 'operators': forecast.to_dict(orient='records')[:5]}, indent=2))


def classify_opportunity(hits):
    h = set(hits)
    opp = []
    if {'drilling','perforación','pozos','wells','rig','pad'} & h:
        opp.append('Drilling rigs')
    if {'workover'} & h:
        opp.append('Workover')
    if {'frac','efrac','e-frac'} & h:
        opp.append('E-frac / stimulation')
    if {'venting','emissions','emisiones'} & h:
        opp.append('Venting / emissions')
    if not opp:
        opp.append('Strategic monitoring')
    return '; '.join(opp)

if __name__ == '__main__':
    main()
