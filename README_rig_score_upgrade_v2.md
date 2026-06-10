# Rig Demand Intelligence Upgrade V2

This upgrade expands the investor crawler to include additional operators, aliases, area-level signal aggregation, and a visible Rig Demand Score methodology.

## Files

1. `investor_crawler_v2.py`  
   Replace your current `investor_crawler.py` with this file. Rename it to `investor_crawler.py` before uploading to GitHub.

2. `app_rig_score_map_snippet.py`  
   Paste into `app.py` to display:
   - Rig Demand Score definition
   - Operator ranking
   - Geographic map by area
   - Underlying signals

## New generated files

After running the investor workflow, the crawler will write:

- `data/operator_signals.csv`
- `data/operator_forecast.csv`
- `data/operator_area_forecast.csv`
- `data/investor_last_run.json`

## Rig Demand Score definition

0-100 score estimating probability that an operator will require rigs and associated services in the next 6-18 months.

- 40% Permits / EIA evidence
- 30% Investor / CAPEX evidence
- 20% Activity intensity
- 10% Operator tier / core-area relevance

## Operators added

YPF, Vista, Tecpetrol, PAE, Pluspetrol, Shell, Chevron, TotalEnergies, Pampa Energía, CGC, Capex/CAPSA, Phoenix, ExxonMobil, Equinor, Petronas, GeoPark, Harbour/Wintershall, Oilstone, Aconcagua, President, Medanito, Madalena, Kilwer, Selva María.
