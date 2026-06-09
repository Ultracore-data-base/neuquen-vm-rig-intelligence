
import re
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

MAX_BULLETIN_IDS_TO_SCAN = 80
BULLETIN_END_ID = 2050
BULLETIN_START_ID = max(1, BULLETIN_END_ID - MAX_BULLETIN_IDS_TO_SCAN)

SOURCES = [
    {
        "name": "Neuquen Official Bulletin",
        "type": "boletin_range",
        "base": "https://boficial.neuquen.gov.ar/BoletinDetalle?Id={id}",
        "start_id": BULLETIN_START_ID,
        "end_id": BULLETIN_END_ID,
    },
    {
        "name": "Neuquen Environment - EIA con plazo cumplido",
        "type": "html",
        "url": "https://ambiente.neuquen.gov.ar/category/eia-con-plazo-cumplido/",
    },
    {
        "name": "Neuquen Environment - search drilling",
        "type": "html",
        "url": "https://ambiente.neuquen.gov.ar/?s=perforacion",
    },
    {
        "name": "Neuquen Environment - search PAD",
        "type": "html",
        "url": "https://ambiente.neuquen.gov.ar/?s=PAD",
    },
]

KEYWORDS = [
    "licencia ambiental", "perforacion", "perforación", "pozos", "pozo",
    "pad", "informe ambiental", "estudio de impacto ambiental", "e.i.a",
    "vaca muerta", "no convencional", "locacion", "locación",
    "ducto", "linea de conduccion", "línea de conducción",
    "venteo", "venteos", "emisiones", "workover", "fractura", "frac",
]

OPERATORS = [
    "YPF", "VISTA", "TECPETROL", "PAN AMERICAN ENERGY", "PAE", "SHELL",
    "PLUSPETROL", "PAMPA", "TOTAL", "TOTAL AUSTRAL", "CHEVRON",
    "CAPEX", "GEOPARK", "PHOENIX", "OILSTONE", "TANGO", "EXXON",
    "PLUSPETROL CUENCA NEUQUINA", "VM INVERSIONES",
]

SERVICE_TERMS = {
    "DRILLING_RIGS": ["perforacion", "perforación", "pozos", "pad", "locacion", "locación"],
    "WORKOVER": ["workover", "intervencion", "intervención", "reparacion", "reparación"],
    "E_FRAC": ["fractura", "frac", "e-frac", "estimulación", "estimulacion"],
    "LIGHTING_TOWERS": ["iluminacion", "iluminación", "torres de iluminación", "torres de iluminacion"],
    "AIR_CONDITIONING": ["campamento", "oficinas", "aire acondicionado"],
    "VENTING_SOLUTIONS": ["venteo", "venteos", "emisiones", "gas", "captura", "aprovechamiento"],
}

def log(msg):
    print(f"[{datetime.now(timezone.utc).isoformat()}] {msg}", flush=True)

def fetch(url, timeout=10):
    headers = {
        "User-Agent": "Mozilla/5.0 NeuquenRigIntelligenceBot/1.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    r = requests.get(url, timeout=timeout, headers=headers)
    r.raise_for_status()
    return r.text

def clean_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for s in soup(["script", "style"]):
        s.extract()
    text = " ".join(soup.get_text(" ").split())
    return text, soup

def relevant(text):
    t = text.lower()
    return any(k in t for k in KEYWORDS)

def detect_operator(text):
    up = text.upper()
    hits = [op for op in OPERATORS if op in up]
    return hits[0] if hits else "Unknown"

def detect_area(text):
    patterns = [
        r"Área de Concesión\s+([A-ZÁÉÍÓÚÑa-záéíóúñ0-9 .,-]{3,80})",
        r"Area de Concesion\s+([A-ZÁÉÍÓÚÑa-záéíóúñ0-9 .,-]{3,80})",
        r"Área\s+([A-ZÁÉÍÓÚÑa-záéíóúñ0-9 .,-]{3,80})",
        r"Yacimiento\s+([A-ZÁÉÍÓÚÑa-záéíóúñ0-9 .,-]{3,80})",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            return m.group(1).strip(" .,-:;")
    return "Unknown"

def detect_pad(text):
    m = re.search(r"\bPAD[-\s]*([A-Z0-9.-]{1,20})", text, re.I)
    if m:
        return "PAD " + m.group(1)
    m = re.search(r"(Informe Ambiental[^.]{0,120})", text, re.I)
    return m.group(1).strip() if m else "Not specified"

def detect_well_count(text):
    for pattern in [r"(\d+)\s*\(?\w*\)?\s+pozos", r"(\d+)\s+pozos", r"pozos\s*[:\-]?\s*(\d+)"]:
        m = re.search(pattern, text, re.I)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
    return 0

def detect_status(text):
    t = text.lower()
    if "licencia ambiental" in t:
        return "Environmental License Published"
    if "estudio de impacto ambiental" in t or "e.i.a" in t:
        return "EIA Published"
    if "audiencia" in t:
        return "Public Hearing / Participation"
    if "permiso" in t:
        return "Permit Published"
    return "Potential Signal"

def detect_services(text):
    t = text.lower()
    out = []
    for service, terms in SERVICE_TERMS.items():
        if any(term in t for term in terms):
            out.append(service)
    return " / ".join(out) if out else "DRILLING_RIGS"

def signature(row):
    raw = "|".join(str(row.get(k, "")) for k in ["SOURCE_URL", "OPERATOR", "AREA", "PAD_OR_WELLS"])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

def build_row(text, url, source_name):
    today = datetime.now(timezone.utc).date().isoformat()
    return {
        "PUBLICATION_DATE": today,
        "DETECTED_AT": datetime.now(timezone.utc).isoformat(),
        "SOURCE": source_name,
        "SOURCE_URL": url,
        "OPERATOR": detect_operator(text),
        "AREA": detect_area(text),
        "PAD_OR_WELLS": detect_pad(text),
        "PERMITTED_WELLS": detect_well_count(text),
        "PERMIT_STATUS": detect_status(text),
        "SERVICE_OPPORTUNITY": detect_services(text),
        "WELL_TYPE": "Horizontal / probable",
        "RESERVOIR": "Unconventional",
        "FORMATION": "Vaca Muerta",
        "LATITUDE": "",
        "LONGITUDE": "",
        "NOTES": text[:900],
    }

def scan_boletin_range(source):
    rows = []
    total = source["end_id"] - source["start_id"] + 1
    log(f"Scanning Official Bulletin IDs {source['start_id']} to {source['end_id']} ({total} pages max)")
    for n, i in enumerate(range(source["start_id"], source["end_id"] + 1), start=1):
        url = source["base"].format(id=i)
        if n % 10 == 0:
            log(f"Bulletin progress: {n}/{total}")
        try:
            html = fetch(url, timeout=8)
            text, _ = clean_text(html)
            if relevant(text):
                rows.append(build_row(text, url, source["name"]))
        except Exception:
            continue
    log(f"Official Bulletin relevant records found: {len(rows)}")
    return rows

def scan_html_source(source):
    rows = []
    log(f"Scanning HTML source: {source['name']}")
    try:
        html = fetch(source["url"], timeout=12)
        text, soup = clean_text(html)
        if relevant(text):
            rows.append(build_row(text, source["url"], source["name"]))

        links_checked = 0
        for a in soup.find_all("a", href=True):
            if links_checked >= 20:
                break
            link = urljoin(source["url"], a["href"])
            label = " ".join(a.get_text(" ").split())
            if relevant(label) or any(k in link.lower() for k in ["eia", "pad", "perfor", "pozo"]):
                links_checked += 1
                try:
                    h2 = fetch(link, timeout=10)
                    t2, _ = clean_text(h2)
                    if relevant(t2):
                        rows.append(build_row(t2, link, source["name"]))
                except Exception:
                    continue
    except Exception as e:
        log(f"Source failed: {source['name']} | {e}")
    log(f"{source['name']} relevant records found: {len(rows)}")
    return rows

def main():
    log("Crawler started")
    all_rows = []

    for source in SOURCES:
        if source["type"] == "boletin_range":
            all_rows.extend(scan_boletin_range(source))
        elif source["type"] == "html":
            all_rows.extend(scan_html_source(source))

    columns = [
        "PUBLICATION_DATE", "DETECTED_AT", "SOURCE", "SOURCE_URL", "OPERATOR", "AREA",
        "PAD_OR_WELLS", "PERMITTED_WELLS", "PERMIT_STATUS", "SERVICE_OPPORTUNITY",
        "WELL_TYPE", "RESERVOIR", "FORMATION", "LATITUDE", "LONGITUDE", "NOTES", "SIGNATURE"
    ]

    if all_rows:
        df = pd.DataFrame(all_rows)
        df["SIGNATURE"] = df.apply(signature, axis=1)
        df = df.drop_duplicates("SIGNATURE")
    else:
        df = pd.DataFrame(columns=columns)

    out = DATA_DIR / "permits_pipeline_auto.csv"
    old = pd.read_csv(out) if out.exists() else pd.DataFrame(columns=columns)

    old_sigs = set(old["SIGNATURE"].astype(str)) if "SIGNATURE" in old.columns else set()
    new = df[~df["SIGNATURE"].astype(str).isin(old_sigs)].copy() if "SIGNATURE" in df.columns else df

    combined = pd.concat([old, df], ignore_index=True, sort=False)
    if "SIGNATURE" in combined.columns:
        combined = combined.drop_duplicates("SIGNATURE")
    combined.to_csv(out, index=False)

    if not new.empty:
        changes_path = DATA_DIR / "changes_log.csv"
        new["CHANGE_TYPE"] = "NEW_PERMIT_SIGNAL"
        new["COMMERCIAL_RELEVANCE"] = new["SERVICE_OPPORTUNITY"]
        old_changes = pd.read_csv(changes_path) if changes_path.exists() else pd.DataFrame()
        changes = pd.concat([old_changes, new], ignore_index=True, sort=False)
        changes.to_csv(changes_path, index=False)

    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "records_total": int(len(combined)),
        "records_new": int(len(new)),
        "sources_scanned": [s["name"] for s in SOURCES],
        "status": "ok",
    }
    (DATA_DIR / "last_run.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log(json.dumps(summary, indent=2))
    log("Crawler finished")

if __name__ == "__main__":
    main()
