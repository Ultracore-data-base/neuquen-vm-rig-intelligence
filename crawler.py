
import re
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

WFS_BASE = "https://hidrocarburos.energianeuquen.gob.ar/geoserver/Hidrocarburos/wfs"
POZOS_VM_LAYER = "Hidrocarburos:Pozos_VM"

# Official/public sources.
SOURCES = [
    {
        "name": "Neuquen Official Bulletin",
        "type": "boletin_range",
        "base": "https://boficial.neuquen.gov.ar/BoletinDetalle?Id={id}",
        "start_id": 1650,
        "end_id": 2050
    },
    {
        "name": "Neuquen Environment - EIA con plazo cumplido",
        "type": "html",
        "url": "https://ambiente.neuquen.gov.ar/category/eia-con-plazo-cumplido/"
    },
    {
        "name": "Neuquen Environment - search drilling",
        "type": "html",
        "url": "https://ambiente.neuquen.gov.ar/?s=perforacion"
    },
    {
        "name": "Neuquen Environment - search PAD",
        "type": "html",
        "url": "https://ambiente.neuquen.gov.ar/?s=PAD"
    },
    {
        "name": "Neuquen Hydrocarbons GIS",
        "type": "wfs",
        "url": WFS_BASE
    }
]

KEYWORDS = [
    "licencia ambiental", "perforacion", "perforación", "pozos", "pozo",
    "pad", "informe ambiental", "estudio de impacto ambiental", "e.i.a",
    "vaca muerta", "no convencional", "locacion", "locación",
    "ducto", "linea de conduccion", "línea de conducción",
    "venteo", "venteos", "emisiones", "workover", "fractura", "frac"
]

OPERATORS = [
    "YPF", "VISTA", "TECPETROL", "PAN AMERICAN ENERGY", "PAE", "SHELL",
    "PLUSPETROL", "PAMPA", "TOTAL", "TOTAL AUSTRAL", "CHEVRON",
    "CAPEX", "GEOPARK", "PHOENIX", "OILSTONE", "TANGO", "EXXON",
    "PLUSPETROL CUENCA NEUQUINA", "VM INVERSIONES"
]

SERVICE_TERMS = {
    "DRILLING_RIGS": ["perforacion", "perforación", "pozos", "pad", "locacion", "locación"],
    "WORKOVER": ["workover", "intervencion", "intervención", "reparacion", "reparación"],
    "E_FRAC": ["fractura", "frac", "e-frac", "estimulación", "estimulacion"],
    "LIGHTING_TOWERS": ["iluminacion", "iluminación", "torres de iluminación", "torres de iluminacion"],
    "AIR_CONDITIONING": ["campamento", "oficinas", "aire acondicionado"],
    "VENTING_SOLUTIONS": ["venteo", "venteos", "emisiones", "gas", "captura", "aprovechamiento"]
}

def fetch(url, timeout=45):
    headers = {"User-Agent": "Mozilla/5.0 NeuquenRigIntelligenceBot/1.0"}
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
    if hits:
        return hits[0]
    # generic fallback near proposed by/propuesto por
    m = re.search(r"propuesto por\s+([A-ZÁÉÍÓÚÑ0-9 .,&-]{3,80})", up, re.I)
    return m.group(1).strip(" .,-") if m else "Unknown"

def detect_area(text):
    patterns = [
        r"Área de Concesión\s+([A-ZÁÉÍÓÚÑa-záéíóúñ0-9 .,-]{3,80})",
        r"Area de Concesion\s+([A-ZÁÉÍÓÚÑa-záéíóúñ0-9 .,-]{3,80})",
        r"Área\s+([A-ZÁÉÍÓÚÑa-záéíóúñ0-9 .,-]{3,80})",
        r"Yacimiento\s+([A-ZÁÉÍÓÚÑa-záéíóúñ0-9 .,-]{3,80})",
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
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
    patterns = [
        r"(\d+)\s*\(?\w*\)?\s+pozos",
        r"(\d+)\s+pozos",
        r"pozos\s*[:\-]?\s*(\d+)",
        r"(\d+)\s+PADs?.{0,40}?(\d+)\s+pozos"
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            nums = [int(x) for x in m.groups() if str(x).isdigit()]
            if len(nums) >= 2 and "pad" in p.lower():
                return nums[0] * nums[1]
            if nums:
                return nums[0]
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
    raw = "|".join(str(row.get(k, "")) for k in ["SOURCE_URL", "OPERATOR", "AREA", "PAD_OR_WELLS", "PUBLICATION_DATE"])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

def scan_boletin_range(source):
    rows = []
    for i in range(source["start_id"], source["end_id"] + 1):
        url = source["base"].format(id=i)
        try:
            html = fetch(url, timeout=20)
            text, soup = clean_text(html)
            if not relevant(text):
                continue
            rows.append(build_row(text, url, source["name"]))
        except Exception:
            continue
    return rows

def scan_html_source(source):
    rows = []
    try:
        html = fetch(source["url"], timeout=30)
        text, soup = clean_text(html)
        if relevant(text):
            rows.append(build_row(text, source["url"], source["name"]))
        for a in soup.find_all("a", href=True):
            link = urljoin(source["url"], a["href"])
            label = " ".join(a.get_text(" ").split())
            if relevant(label) or any(k in link.lower() for k in ["eia", "pad", "perfor", "pozo"]):
                try:
                    h2 = fetch(link, timeout=30)
                    t2, _ = clean_text(h2)
                    if relevant(t2):
                        rows.append(build_row(t2, link, source["name"]))
                except Exception:
                    pass
    except Exception:
        pass
    return rows

def build_row(text, url, source_name):
    operator = detect_operator(text)
    area = detect_area(text)
    pad = detect_pad(text)
    wells = detect_well_count(text)
    status = detect_status(text)
    services = detect_services(text)
    today = datetime.now(timezone.utc).date().isoformat()
    short = text[:900]
    return {
        "PUBLICATION_DATE": today,
        "DETECTED_AT": datetime.now(timezone.utc).isoformat(),
        "SOURCE": source_name,
        "SOURCE_URL": url,
        "OPERATOR": operator,
        "AREA": area,
        "PAD_OR_WELLS": pad,
        "PERMITTED_WELLS": wells,
        "PERMIT_STATUS": status,
        "SERVICE_OPPORTUNITY": services,
        "WELL_TYPE": "Horizontal / probable",
        "RESERVOIR": "Unconventional",
        "FORMATION": "Vaca Muerta",
        "LATITUDE": "",
        "LONGITUDE": "",
        "NOTES": short
    }

def load_wells():
    params = {
        "service": "WFS",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeName": POZOS_VM_LAYER,
        "outputFormat": "csv",
    }
    r = requests.get(WFS_BASE, params=params, timeout=120)
    r.raise_for_status()
    df = pd.read_csv(StringIO(r.text))
    df.columns = [str(c).strip().upper() for c in df.columns]
    return df

def add_area_centroids(rows, wells):
    if wells.empty or "LATITUD" not in wells.columns or "LONGITUD" not in wells.columns:
        return rows
    wells["LATITUD"] = pd.to_numeric(wells["LATITUD"], errors="coerce")
    wells["LONGITUD"] = pd.to_numeric(wells["LONGITUD"], errors="coerce")
    area_col = "AREA_LEGAL" if "AREA_LEGAL" in wells.columns else "FIELD_NAME"
    if area_col not in wells.columns:
        return rows
    cent = wells.dropna(subset=["LATITUD", "LONGITUD"]).groupby(area_col)[["LATITUD", "LONGITUD"]].median().reset_index()
    cent["KEY"] = cent[area_col].astype(str).str.upper()
    lookup = {r["KEY"]: (r["LATITUD"], r["LONGITUD"]) for _, r in cent.iterrows()}
    for row in rows:
        key = str(row.get("AREA", "")).upper()
        # exact first, then contains
        if key in lookup:
            row["LATITUDE"], row["LONGITUDE"] = lookup[key]
        else:
            for k, v in lookup.items():
                if key and (key in k or k in key):
                    row["LATITUDE"], row["LONGITUDE"] = v
                    break
    return rows

def main():
    all_rows = []
    for source in SOURCES:
        if source["type"] == "boletin_range":
            all_rows.extend(scan_boletin_range(source))
        elif source["type"] == "html":
            all_rows.extend(scan_html_source(source))

    df = pd.DataFrame(all_rows)
    if df.empty:
        df = pd.DataFrame(columns=[
            "PUBLICATION_DATE","DETECTED_AT","SOURCE","SOURCE_URL","OPERATOR","AREA","PAD_OR_WELLS",
            "PERMITTED_WELLS","PERMIT_STATUS","SERVICE_OPPORTUNITY","WELL_TYPE","RESERVOIR","FORMATION",
            "LATITUDE","LONGITUDE","NOTES","SIGNATURE"
        ])
    else:
        df["SIGNATURE"] = df.apply(signature, axis=1)
        df = df.drop_duplicates("SIGNATURE")

    try:
        wells = load_wells()
        rows = add_area_centroids(df.to_dict("records"), wells)
        df = pd.DataFrame(rows)
    except Exception:
        pass

    out = DATA_DIR / "permits_pipeline_auto.csv"
    old = pd.read_csv(out) if out.exists() else pd.DataFrame(columns=df.columns)

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
        if changes_path.exists:
            old_changes = pd.read_csv(changes_path) if changes_path.exists() else pd.DataFrame()
            changes = pd.concat([old_changes, new], ignore_index=True, sort=False)
        else:
            changes = new
        changes.to_csv(changes_path, index=False)

    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "records_total": len(combined),
        "records_new": len(new),
        "sources_scanned": [s["name"] for s in SOURCES]
    }
    (DATA_DIR / "last_run.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
