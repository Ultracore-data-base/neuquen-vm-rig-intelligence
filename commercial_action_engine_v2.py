import pandas as pd


def _norm(value):
    return str(value or "").strip().upper()


def _num(value, default=0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _get_match(df, area, operator, area_col="Area", operator_col="Operator"):
    if df is None or df.empty or area_col not in df.columns:
        return None

    tmp = df.copy()
    tmp["_area_key"] = tmp[area_col].apply(_norm)
    match = tmp[tmp["_area_key"] == _norm(area)]

    if not match.empty and operator and operator_col in tmp.columns:
        match["_operator_key"] = match[operator_col].apply(_norm)
        exact = match[match["_operator_key"] == _norm(operator)]
        if not exact.empty:
            match = exact

    if match.empty:
        return None

    return match.iloc[0].to_dict()


def build_commercial_action(
    area,
    operator,
    rig_expansion=None,
    rig_commitments=None,
    contract_intelligence=None,
    capital_program=None,
):
    rig = _get_match(rig_expansion, area, operator, "Area", "Operator")
    contract = _get_match(contract_intelligence, area, operator, "Area", "Operator")

    commitment = None
    if rig_commitments is not None and not rig_commitments.empty and "area" in rig_commitments.columns:
        tmp = rig_commitments.copy()
        tmp["_area_key"] = tmp["area"].apply(_norm)
        match = tmp[tmp["_area_key"] == _norm(area)]
        if not match.empty and "operator" in tmp.columns:
            match["_operator_key"] = match["operator"].apply(_norm)
            exact = match[match["_operator_key"] == _norm(operator)]
            if not exact.empty:
                match = exact
        if not match.empty:
            commitment = match.iloc[0].to_dict()

    capex = None
    if capital_program is not None and not capital_program.empty and "operator" in capital_program.columns:
        tmp = capital_program.copy()
        tmp["_operator_key"] = tmp["operator"].apply(_norm)
        op = _norm(operator)
        match = tmp[tmp["_operator_key"].apply(lambda x: op in x or x in op)]
        if not match.empty:
            capex = match.iloc[0].to_dict()

    rig_expansion_score = _num(rig.get("Rig Expansion Score") if rig else 0)
    estimated_gap = _num(rig.get("Estimated Gap") if rig else 0)
    active_rigs = _num(commitment.get("active_rigs") if commitment else 0)
    incoming_rigs = _num(commitment.get("incoming_rigs") if commitment else 0)
    owned_rigs = _num(commitment.get("owned_rigs_committed") if commitment else 0)
    new_rig_penalty = _num(commitment.get("new_rig_penalty") if commitment else 0)
    months_remaining = _num(contract.get("Months Remaining") if contract else -1)
    rebid = _num(contract.get("Rebid Opportunity") if contract else 0)
    om = _num(contract.get("O&M Opportunity") if contract else 0)
    capital_score = _num(capex.get("capital_score") if capex else 0)

    secured_supply = active_rigs + incoming_rigs + owned_rigs

    if secured_supply >= 4 and new_rig_penalty >= 70 and rig_expansion_score <= 35:
        action = "Do not offer new rigs"
        priority = "Services / O&M"
        rationale = "Fleet already covered and contract lock-in is high."
        services = ["O&M", "Rig management", "Maintenance", "Lighting Towers", "HVAC", "Venting", "E-Frac support"]
    elif months_remaining >= 0 and months_remaining <= 12 and rebid >= 50:
        action = "Prepare rebid approach"
        priority = "High"
        rationale = "Contract renewal window is approaching."
        services = ["Replacement rig", "O&M", "Rig performance audit", "Maintenance"]
    elif rig_expansion_score >= 70 and estimated_gap >= 1:
        action = "Pursue rig opportunity"
        priority = "High"
        rationale = "Expansion score and estimated rig gap indicate potential demand."
        services = ["1500HP Walking Rig", "Rig support", "Lighting Towers", "HVAC"]
    elif capital_score >= 80 and rig_expansion_score >= 40:
        action = "Commercial prospecting"
        priority = "Medium / High"
        rationale = "Strong capital program supports future drilling or services demand."
        services = ["Rig discussion", "O&M", "Workover", "E-Frac support", "Lighting Towers"]
    elif om >= 60:
        action = "Offer O&M and rig services"
        priority = "Medium"
        rationale = "Operational intensity and third-party rig exposure support services opportunity."
        services = ["O&M", "Rig management", "Maintenance", "Spare parts", "Crew support"]
    else:
        action = "Monitor"
        priority = "Medium / Low"
        rationale = "No immediate new-rig gap detected. Maintain intelligence watch."
        services = ["Workover", "Lighting Towers", "HVAC", "Venting"]

    return {
        "Area": area,
        "Operator": operator,
        "Recommended Action": action,
        "Priority": priority,
        "Rationale": rationale,
        "Suggested Services": ", ".join(services),
        "New Rig Opportunity": int(round(rig_expansion_score)),
        "Active / Secured Rigs": int(round(secured_supply)),
        "Rebid Opportunity": int(round(rebid)),
        "O&M Opportunity": int(round(om)),
        "Capital Score": int(round(capital_score)),
    }


def commercial_action_html(
    area,
    operator,
    rig_expansion=None,
    rig_commitments=None,
    contract_intelligence=None,
    capital_program=None,
):
    info = build_commercial_action(
        area,
        operator,
        rig_expansion,
        rig_commitments,
        contract_intelligence,
        capital_program,
    )

    return f"""
    <div class="detail-row">
    <span>Recommended Action</span>
    <span>{info.get("Recommended Action", "-")}</span>
    </div>

    <div class="detail-row">
    <span>Commercial Focus</span>
    <span>{info.get("Priority", "-")}</span>
    </div>

    <div class="detail-row">
    <span>Opportunity Score</span>
    <span>{max(
        int(info.get("New Rig Opportunity",0)),
        int(info.get("Rebid Opportunity",0)),
        int(info.get("O&M Opportunity",0))
    )}</span>
    </div>

    <div class="service-badge-wrap">
    {
    "".join(
    f'<span class="service-badge">{s.strip()}</span>'
    for s in str(info.get("Suggested Services","")).split(",")
    if s.strip()
)
    }
    </div>
    """
