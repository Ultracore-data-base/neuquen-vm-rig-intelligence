
import pandas as pd

def normalize_score(value, max_value=100):
    try:
        return max(0, min(float(value), max_value))
    except Exception:
        return 0

def rig_demand_score(permit_score=0, capex_score=0, activity_score=0, operator_score=0):
    """Weighted 0-100 Rig Demand Score."""
    return round(
        0.40 * normalize_score(permit_score) +
        0.30 * normalize_score(capex_score) +
        0.20 * normalize_score(activity_score) +
        0.10 * normalize_score(operator_score), 1
    )

def rig_coverage_score(contracted_rigs_score=0, owned_or_leased_score=0, term_score=0, confidence_score=0):
    """Weighted 0-100 Rig Coverage Score."""
    return round(
        0.40 * normalize_score(contracted_rigs_score) +
        0.25 * normalize_score(owned_or_leased_score) +
        0.20 * normalize_score(term_score) +
        0.15 * normalize_score(confidence_score), 1
    )

def open_rig_opportunity_score(demand_score, coverage_score, expiry_bonus=0, multiservice_bonus=0):
    """Demand not yet covered by known rigs/providers."""
    return round(max(0, normalize_score(demand_score) - normalize_score(coverage_score) + normalize_score(expiry_bonus, 20) + normalize_score(multiservice_bonus, 15)), 1)

def service_opportunity_score(base_signal=0, basin_fit=0, operator_fit=0, adjacent_services=0, evidence_confidence=0):
    """Generic score for workover, frac, e-frac, venting, HVAC, lighting, power, water, facilities."""
    return round(
        0.35 * normalize_score(base_signal) +
        0.20 * normalize_score(basin_fit) +
        0.15 * normalize_score(operator_fit) +
        0.15 * normalize_score(adjacent_services) +
        0.15 * normalize_score(evidence_confidence), 1
    )
