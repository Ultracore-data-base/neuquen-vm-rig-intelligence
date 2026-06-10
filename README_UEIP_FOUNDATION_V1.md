# Ultracore Energy Intelligence Platform (UEIP) — Foundation v1

Generated: 2026-06-10T02:21:53

This package converts the current Neuquén/Vaca Muerta dashboard into an Argentina-first, LATAM-ready data foundation.

## What is included

`data/`
- countries.csv
- basin_master.csv
- province_master.csv
- operator_master.csv
- operator_aliases.csv
- area_master.csv
- service_master.csv
- rig_provider_master.csv
- score_definitions.csv
- service_opportunity_rules.csv
- operator_rig_strategy.csv
- source_registry.csv

`snippets/`
- app_national_master_tabs_snippet.py
- ueip_scoring_engine.py

## Strategic goal

Answer the commercial question:

> Which operator, in which area, in which basin, in which time horizon, will need which service, and who is the incumbent provider?

## Notes

- `area_master.csv` is a seed layer, not a final authoritative concession database.
- The next step is to enrich `area_master.csv` from national official concession datasets and provincial GIS/Boletín/Environment sources.
- Fields include confidence and source_note to prevent false precision.
- Argentina is Phase 1; the country/basin model is already LATAM-ready.
