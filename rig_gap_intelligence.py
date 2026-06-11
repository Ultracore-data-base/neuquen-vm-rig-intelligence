def parse_forecast_range(forecast_text):
    text = str(forecast_text or "").lower().replace("–", "-").replace("—", "-")

    if "2-4" in text or "2 - 4" in text:
        return 2, 4
    if "1-3" in text or "1 - 3" in text:
        return 1, 3
    if "1-2" in text or "1 - 2" in text:
        return 1, 2
    if "watchlist" in text:
        return 0, 1
    if "low" in text:
        return 0, 0

    return 0, 0


def safe_int(value):
    try:
        return int(float(value))
    except Exception:
        return None


def rig_gap_status(forecast_text, current_rigs):
    min_required, max_required = parse_forecast_range(forecast_text)
    current = safe_int(current_rigs)

    if current is None:
        if max_required >= 3:
            return {
                "coverage": "Unknown",
                "gap": "To verify",
                "status": "High Priority Verification",
                "priority": "High",
            }
        if max_required >= 1:
            return {
                "coverage": "Unknown",
                "gap": "To verify",
                "status": "Intelligence Required",
                "priority": "Medium",
            }
        return {
            "coverage": "Unknown",
            "gap": "-",
            "status": "Low probability",
            "priority": "Low",
        }

    gap = max_required - current

    if gap >= 2:
        status = "Open rig opportunity"
        priority = "High"
    elif gap == 1:
        status = "Potential incremental rig"
        priority = "Medium"
    elif gap == 0:
        status = "Balanced coverage"
        priority = "Medium"
    else:
        status = "Covered / no immediate gap"
        priority = "Low"

    return {
        "coverage": str(current),
        "gap": str(max(gap, 0)),
        "status": status,
        "priority": priority,
    }


def rig_gap_html(forecast_text, contractor_info):
    current_rigs = None

    if contractor_info:
        current_rigs = contractor_info.get("rig_count", None)

    result = rig_gap_status(forecast_text, current_rigs)

    return f"""
      <div class="detail-row"><span>Current Coverage</span><span>{result.get("coverage", "-")}</span></div>
      <div class="detail-row"><span>Forecast Range</span><span>{forecast_text}</span></div>
      <div class="detail-row"><span>Estimated Gap</span><span>{result.get("gap", "-")}</span></div>
      <div class="detail-row"><span>Gap Status</span><span>{result.get("status", "-")}</span></div>
      <div class="detail-row"><span>Commercial Priority</span><span>{result.get("priority", "-")}</span></div>
    """
