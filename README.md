
# Neuquen / Vaca Muerta Drilling Intelligence Dashboard

Streamlit MVP for Dustin / Stamper.

## What it does
- Pulls official Vaca Muerta wells from Neuquen GeoServer WFS.
- Shows operator ranking, area ranking and a map.
- Allows upload of Official Bulletin / Environment permit pipeline.
- Scores forward-looking rig opportunity.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Cloud
1. Create a GitHub repository.
2. Upload app.py, requirements.txt, permits_template.csv.
3. Go to Streamlit Cloud.
4. New app > select repository > main file: app.py.
5. Deploy.

## Data source
Neuquen GeoServer WFS:
https://hidrocarburos.energianeuquen.gob.ar/geoserver/Hidrocarburos/wfs

Layer used:
Hidrocarburos:Pozos_VM

## Permit CSV format
PUBLICATION_DATE, OPERATOR, AREA, PAD_OR_WELLS, PERMITTED_WELLS, PERMIT_STATUS, SOURCE_URL, NOTES
