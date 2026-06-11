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


def _expiry_score(months):
    months = _num(months)
    if months <= 0:
        return 20
    if months <= 6:
        return 90
    if months <= 12:
        return 70
    if months <= 24:
        return 45
    return 20


def _service_bucket(score):
    score = _num(score)
    if score >= 80:
        return "High O&M / Service Target"
    if score >= 60:
        return "Service Target"
    if score >= 40:
        return "Monitor Service"
    return "Low"


def rig_commitment_context(area, operator, rig_commitments):
    if rig_commitments is None or rig_commitments.empty:
        return None

    df = rig_commitments.copy()

    if "area" not in df.columns:
        return None

    df["_area_key"] = df["area"].apply(_norm)
    match = df[df["_area_key"] == _norm(area)]

    if not match.empty and operator and "operator" in df.columns:
        match["_operator_key"] = match["operator"].apply(_norm)
        exact = match[match["_operator_key"] == _norm(operator)]
        if not exact.empty:
            match = exact

    if match.empty:
        return None

    row = match.iloc[0].to_dict()

    if "expiry_opportunity_score" not in row or pd.isna(row.get("expiry_opportunity_score")):
        row["expiry_opportunity_score"] = _expiry_score(row.get("months_to_expiry", 0))

    return row


def rig_commitment_html(area, operator, rig_commitments):
    info = rig_commitment_context(area, operator, rig_commitments)

    if not info:
        return """
        <div class="detail-row"><span>Rig Supply</span><span>To verify</span></div>
        <div class="detail-row"><span>Contract Expiry</span><span>-</span></div>
        <div class="detail-row"><span>New Rig Penalty</span><span>-</span></div>
        <div class="detail-row"><span>O&M Opportunity</span><span>-</span></div>
        """

    active = int(_num(info.get("active_rigs", 0)))
    owned = int(_num(info.get("owned_rigs_committed", 0)))
    incoming = int(_num(info.get("incoming_rigs", 0)))
    penalty = int(_num(info.get("new_rig_penalty", info.get("commitment_penalty", 0))))
    service_score = int(_num(info.get("third_party_rig_service_score", 0)))
    expiry_score = int(_num(info.get("expiry_opportunity_score", _expiry_score(info.get("months_to_expiry", 0)))))

    return f"""
    <div class="detail-row"><span>Known Contractor</span><span>{info.get("known_contractor", "-")}</span></div>
    <div class="detail-row"><span>Active Rigs</span><span>{active}</span></div>
    <div class="detail-row"><span>Owned/Committed</span><span>{owned}</span></div>
    <div class="detail-row"><span>Incoming Rigs</span><span>{incoming}</span></div>
    <div class="detail-row"><span>Contract Expiry</span><span>{info.get("contract_expiry", "-")}</span></div>
    <div class="detail-row"><span>Expiry Opportunity</span><span>{expiry_score}</span></div>
    <div class="detail-row"><span>New Rig Penalty</span><span>{penalty}</span></div>
    <div class="detail-row"><span>O&M / Support</span><span>{service_score}</span></div>
    <div class="detail-row"><span>Service Bucket</span><span>{_service_bucket(service_score)}</span></div>
    """


def apply_rig_commitment_penalty(rig_expansion_df, rig_commitments):
    if rig_expansion_df is None or rig_expansion_df.empty:
        return pd.DataFrame()

    out = rig_expansion_df.copy()

    if rig_commitments is None or rig_commitments.empty:
        out["Rig Supply Penalty"] = 0
        out["Third Party Rig Service Score"] = 0
        return out

    commits = rig_commitments.copy()

    if "area" not in commits.columns:
        out["Rig Supply Penalty"] = 0
        out["Third Party Rig Service Score"] = 0
        return out

    out["_area_key"] = out["Area"].apply(_norm)
    out["_operator_key"] = out["Operator"].apply(_norm)

    commits["_area_key"] = commits["area"].apply(_norm)
    commits["_operator_key"] = commits["operator"].apply(_norm) if "operator" in commits.columns else ""

    cols = [
        "_area_key",
        "_operator_key",
        "active_rigs",
        "owned_rigs_committed",
        "incoming_rigs",
        "contract_expiry",
        "months_to_expiry",
        "expiry_opportunity_score",
        "new_rig_penalty",
        "third_party_rig_service_score",
        "commitment_note",
    ]
    cols = [c for c in cols if c in commits.columns]

    out = out.merge(
        commits[cols].drop_duplicates(["_area_key", "_operator_key"]),
        on=["_area_key", "_operator_key"],
        how="left"
    )

    out["new_rig_penalty"] = pd.to_numeric(out.get("new_rig_penalty", 0), errors="coerce").fillna(0)
    out["third_party_rig_service_score"] = pd.to_numeric(out.get("third_party_rig_service_score", 0), errors="coerce").fillna(0)
    out["expiry_opportunity_score"] = pd.to_numeric(out.get("expiry_opportunity_score", 0), errors="coerce").fillna(0)

    # Contract expiry partially offsets the supply penalty because an expiring contract creates a future opening.
    effective_penalty = (out["new_rig_penalty"] - out["expiry_opportunity_score"] * 0.35).clip(lower=0)

    out["Rig Supply Penalty"] = effective_penalty.round(0).astype(int)
    out["Third Party Rig Service Score"] = out["third_party_rig_service_score"].round(0).astype(int)

    base_score = pd.to_numeric(out["Rig Expansion Score"], errors="coerce").fillna(0)
    out["Rig Expansion Score Raw"] = base_score.round(0).astype(int)
    out["Rig Expansion Score"] = (base_score - out["Rig Supply Penalty"]).clip(lower=0, upper=100).round(0).astype(int)

    out["Service Opportunity Note"] = out.apply(
        lambda r: "Existing rigs: prioritize O&M, maintenance, performance control and rig management"
        if _num(r.get("Third Party Rig Service Score")) >= 60
        else r.get("Commercial Note", ""),
        axis=1
    )

    clean_cols = [c for c in out.columns if not c.startswith("_")]
    out = out[clean_cols]

    return out.sort_values(
        ["Rig Expansion Score", "Third Party Rig Service Score", "Estimated Gap"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
