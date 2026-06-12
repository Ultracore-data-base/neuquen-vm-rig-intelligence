import pandas as pd
from datetime import datetime


def _norm(value):
    return str(value or "").strip().upper()


def _num(value, default=0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def months_remaining(date_value):
    if date_value is None or str(date_value).strip() == "":
        return None
    try:
        end = pd.to_datetime(date_value, errors="coerce")
        if pd.isna(end):
            return None
        today = pd.Timestamp(datetime.today().date())
        return int(round((pd.Timestamp(end) - today).days / 30.44))
    except Exception:
        return None


def expiry_opportunity_score(months, renewal_option="Unknown"):
    if months is None:
        base = 35
    elif months > 24:
        base = 10
    elif months > 18:
        base = 25
    elif months > 12:
        base = 40
    elif months > 6:
        base = 65
    else:
        base = 90

    renewal = _norm(renewal_option)
    if renewal == "YES":
        base -= 15
    elif renewal == "NO":
        base += 10

    return int(max(0, min(100, round(base))))


def _category(score):
    score = _num(score)
    if score >= 75:
        return "Pursue"
    if score >= 50:
        return "Prepare"
    if score >= 25:
        return "Monitor"
    return "Closed"


def _action(score, renewal_option):
    score = _num(score)
    renewal = _norm(renewal_option)
    if score >= 75:
        return "Start commercial approach"
    if score >= 50:
        return "Prepare rebid positioning"
    if score >= 25:
        return "Monitor renewal option" if renewal == "YES" else "Track expiry window"
    return "Low new-rig priority; focus services"


def _key(df, area_col, op_col):
    out = df.copy()
    out["_area_key"] = out[area_col].apply(_norm) if area_col in out.columns else ""
    out["_operator_key"] = out[op_col].apply(_norm) if op_col in out.columns else ""
    return out


def build_contract_intelligence(contracts, observed_activity=None, tender_probability=None, forecast_intelligence=None, rig_expansion=None):
    if contracts is None or contracts.empty:
        return pd.DataFrame()

    df = contracts.copy()
    for col in ["operator","area","contractor","rig_type","rig_count","contract_start","contract_end","renewal_option","status","contract_note"]:
        if col not in df.columns:
            df[col] = ""

    df["months_remaining"] = df["contract_end"].apply(months_remaining)
    df["expiry_opportunity"] = df.apply(lambda r: expiry_opportunity_score(r.get("months_remaining"), r.get("renewal_option")), axis=1)
    df = _key(df, "area", "operator")

    if observed_activity is not None and not observed_activity.empty and "area" in observed_activity.columns:
        obs = _key(observed_activity, "area", "operator")
        cols = [c for c in ["_area_key","_operator_key","operational_observed_score","production_signal","drilling_signal","well_status_signal","trend_signal"] if c in obs.columns]
        df = df.merge(obs[cols].drop_duplicates(["_area_key","_operator_key"]), on=["_area_key","_operator_key"], how="left")

    if tender_probability is not None and not tender_probability.empty and "Area" in tender_probability.columns:
        ten = _key(tender_probability, "Area", "Operator")
        cols = [c for c in ["_area_key","_operator_key","Tender Probability (%)","Estimated Gap","Confidence","Expected Timing"] if c in ten.columns]
        df = df.merge(ten[cols].drop_duplicates(["_area_key","_operator_key"]), on=["_area_key","_operator_key"], how="left")

    if forecast_intelligence is not None and not forecast_intelligence.empty and "Area" in forecast_intelligence.columns:
        fc = _key(forecast_intelligence, "Area", "Operator")
        cols = [c for c in ["_area_key","_operator_key","Forecast Activity 12m","Forecast Activity 24m","Delta 12m","Rig Demand Trend"] if c in fc.columns]
        df = df.merge(fc[cols].drop_duplicates(["_area_key","_operator_key"]), on=["_area_key","_operator_key"], how="left")

    if rig_expansion is not None and not rig_expansion.empty and "Area" in rig_expansion.columns:
        re = _key(rig_expansion, "Area", "Operator")
        cols = [c for c in ["_area_key","_operator_key","Rig Expansion Score","Third Party Rig Service Score","Rig Supply Penalty","Service Opportunity Note"] if c in re.columns]
        df = df.merge(re[cols].drop_duplicates(["_area_key","_operator_key"]), on=["_area_key","_operator_key"], how="left")

    for col in ["operational_observed_score","Tender Probability (%)","Forecast Activity 12m","Rig Expansion Score","Third Party Rig Service Score"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["rebid_opportunity"] = (
        df["expiry_opportunity"] * 0.40
        + df["operational_observed_score"] * 0.20
        + df["Tender Probability (%)"] * 0.15
        + df["Forecast Activity 12m"] * 0.15
        + df["Rig Expansion Score"] * 0.10
    ).round(0).clip(lower=0, upper=100).astype(int)

    df["om_opportunity"] = (
        df["operational_observed_score"] * 0.40
        + df["Third Party Rig Service Score"] * 0.35
        + pd.to_numeric(df["rig_count"], errors="coerce").fillna(0).clip(upper=10) * 2.5
    ).round(0).clip(lower=0, upper=100).astype(int)

    df["category"] = df["rebid_opportunity"].apply(_category)
    df["recommended_action"] = df.apply(lambda r: _action(r.get("rebid_opportunity"), r.get("renewal_option")), axis=1)

    result = pd.DataFrame({
        "Area": df["area"],
        "Operator": df["operator"],
        "Current Contractor": df["contractor"],
        "Rig Type": df["rig_type"],
        "Rig Count": pd.to_numeric(df["rig_count"], errors="coerce").fillna(0).astype(int),
        "Contract Start": df["contract_start"],
        "Contract End": df["contract_end"],
        "Months Remaining": df["months_remaining"].fillna(-1).astype(int),
        "Renewal Option": df["renewal_option"],
        "Status": df["status"],
        "Expiry Opportunity": df["expiry_opportunity"],
        "Rebid Opportunity": df["rebid_opportunity"],
        "O&M Opportunity": df["om_opportunity"],
        "Category": df["category"],
        "Recommended Action": df["recommended_action"],
        "Contract Note": df["contract_note"],
    })

    return result.sort_values(["Rebid Opportunity","O&M Opportunity","Expiry Opportunity"], ascending=[False, False, False]).reset_index(drop=True)


def contract_context_for_area(area, operator, contract_intelligence):
    if contract_intelligence is None or contract_intelligence.empty:
        return None
    df = contract_intelligence.copy()
    if "Area" not in df.columns:
        return None
    df["_area_key"] = df["Area"].apply(_norm)
    match = df[df["_area_key"] == _norm(area)]
    if not match.empty and operator and "Operator" in df.columns:
        match["_operator_key"] = match["Operator"].apply(_norm)
        exact = match[match["_operator_key"] == _norm(operator)]
        if not exact.empty:
            match = exact
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def contract_intelligence_html(area, operator, contract_intelligence):
    info = contract_context_for_area(area, operator, contract_intelligence)
    if not info:
        return """
        <div class="detail-row"><span>Current Contractor</span><span>To verify</span></div>
        <div class="detail-row"><span>Contract End</span><span>-</span></div>
        <div class="detail-row"><span>Rebid Opportunity</span><span>-</span></div>
        <div class="detail-row"><span>O&M Opportunity</span><span>-</span></div>
        """
    return f"""
    <div class="detail-row"><span>Current Contractor</span><span>{info.get("Current Contractor", "-")}</span></div>
    <div class="detail-row"><span>Contract End</span><span>{info.get("Contract End", "-")}</span></div>
    <div class="detail-row"><span>Months Remaining</span><span>{info.get("Months Remaining", "-")}</span></div>
    <div class="detail-row"><span>Renewal Option</span><span>{info.get("Renewal Option", "-")}</span></div>
    <div class="detail-row"><span>Expiry Opportunity</span><span>{info.get("Expiry Opportunity", "-")}</span></div>
    <div class="detail-row"><span>Rebid Opportunity</span><span>{info.get("Rebid Opportunity", "-")}</span></div>
    <div class="detail-row"><span>O&M Opportunity</span><span>{info.get("O&M Opportunity", "-")}</span></div>
    <div class="detail-row"><span>Category</span><span>{info.get("Category", "-")}</span></div>
    <div class="detail-row"><span>Action</span><span>{info.get("Recommended Action", "-")}</span></div>
    """
