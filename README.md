# Vaca Muerta / Neuquen Rig & Services Intelligence V3

This dashboard monitors Vaca Muerta drilling activity and forward-looking permit signals for a 10-rig deployment over 3–4 years plus adjacent services: workover, e-frac, lighting towers, air conditioning and venting/productive emissions solutions.

## Core sources

- Official Neuquen GeoServer WFS: `Hidrocarburos:Pozos_VM`
- Neuquen Official Bulletin
- Neuquen Environment Secretariat pages
- Neuquen Hydrocarbons GIS layers

## Main files

- `app.py` — Streamlit dashboard
- `crawler.py` — automatic official-source crawler
- `.github/workflows/daily_update.yml` — daily GitHub Actions automation
- `data/permits_pipeline_auto.csv` — generated permit pipeline
- `data/changes_log.csv` — generated changes / alert log

## Deploy

Streamlit Cloud:
- Repository: `Ultracore-data-base/neuquen-vm-rig-intelligence`
- Branch: `main`
- Main file: `app.py`

## Enable automatic daily updates

1. Push all V3 files to GitHub.
2. Go to GitHub repo > Actions.
3. Enable workflows if GitHub asks.
4. Run `Daily Neuquen Permit Crawler` manually once.
5. After that it runs daily at approx. 08:30 Argentina time.

## Important note

The crawler extracts official public signals with a conservative NLP/regex approach. It should be reviewed and calibrated as more official sources and exact endpoints are discovered.
