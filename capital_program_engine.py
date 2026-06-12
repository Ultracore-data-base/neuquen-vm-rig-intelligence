import pandas as pd


def _normalize(value):
    return str(value or "").strip().upper()


def _guidance_score(guidance):
    guidance = _normalize(guidance)

    if guidance == "GROWTH":
        return 100

    if guidance == "STABLE":
        return 70

    if guidance == "SELECTIVE":
        return 40

    return 50


def _rig_growth_score(signal):
    signal = _normalize(signal)

    if signal == "HIGH":
        return 100

    if signal == "MEDIUM":
        return 70

    if signal == "LOW":
        return 40

    return 50


def build_capital_program(df):

    if df is None or df.empty:
        return pd.DataFrame()

    result = df.copy()

    max_capex = result["capex_usd_mm"].max()
    max_drilling = result["drilling_budget_mm"].max()
    max_completion = result["completion_budget_mm"].max()

    result["capex_score"] = (
        result["capex_usd_mm"] / max_capex * 100
    )

    result["drilling_score"] = (
        result["drilling_budget_mm"] / max_drilling * 100
    )

    result["completion_score"] = (
        result["completion_budget_mm"] / max_completion * 100
    )

    result["guidance_score"] = result["guidance"].apply(
        _guidance_score
    )

    result["rig_growth_score"] = result[
        "rig_growth_signal"
    ].apply(
        _rig_growth_score
    )

    result["capital_score"] = (
        result["capex_score"] * 0.30
        + result["drilling_score"] * 0.40
        + result["completion_score"] * 0.20
        + result["guidance_score"] * 0.05
        + result["rig_growth_score"] * 0.05
    ).round(0)

    return result.sort_values(
        "capital_score",
        ascending=False
    )


def capital_program_html(
    area,
    operator,
    capital_program
):

    if capital_program is None:
        return """
        <div class="detail-row">
            <span>CAPEX</span>
            <span>No Data</span>
        </div>
        """

    if capital_program.empty:
        return """
        <div class="detail-row">
            <span>CAPEX</span>
            <span>No Data</span>
        </div>
        """

    match = capital_program[
        capital_program["operator"]
        .astype(str)
        .str.upper()
        .str.contains(
            str(operator).upper(),
            na=False
        )
    ]

    if match.empty:
        return """
        <div class="detail-row">
            <span>CAPEX</span>
            <span>Not Found</span>
        </div>
        """

    info = match.iloc[0]

    return f"""
    <div class="detail-row">
        <span>CAPEX</span>
        <span>USD {info['capex_usd_mm']:,.0f} MM</span>
    </div>

    <div class="detail-row">
        <span>Drilling Budget</span>
        <span>USD {info['drilling_budget_mm']:,.0f} MM</span>
    </div>

    <div class="detail-row">
        <span>Completion Budget</span>
        <span>USD {info['completion_budget_mm']:,.0f} MM</span>
    </div>

    <div class="detail-row">
        <span>Guidance</span>
        <span>{info['guidance']}</span>
    </div>

    <div class="detail-row">
        <span>Rig Growth</span>
        <span>{info['rig_growth_signal']}</span>
    </div>

    <div class="detail-row">
        <span>Confidence</span>
        <span>{info['confidence']}%</span>
    </div>

    <div class="detail-row">
        <span>Capital Score</span>
        <span>{int(info['capital_score'])}</span>
    </div>
    """
