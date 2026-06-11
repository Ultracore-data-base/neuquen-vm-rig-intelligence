import pandas as pd


def normalize_contractor_name(name):
    text = str(name or "").strip().upper()

    aliases = {
        "HP": "HELMERICH",
        "H&P": "HELMERICH",
        "HELMERICH": "HELMERICH",
        "HELMERICH & PAYNE": "HELMERICH",
        "NABORS": "NABORS",
        "DLS": "DLS",
        "DLS ARCHER": "DLS",
        "SAN ANTONIO": "SAN ANTONIO",
        "SAI": "SAN ANTONIO",
        "ENSIGN": "ENSIGN",
    }

    for key, value in aliases.items():
        if key in text:
            return value

    return text


def contractor_fleet_summary(contractor, rig_fleet):
    if rig_fleet is None or rig_fleet.empty:
        return None

    required = {"provider", "rig_owner", "hp", "walking", "top_drive", "shale_ready"}
    if not required.issubset(rig_fleet.columns):
        return None

    target = normalize_contractor_name(contractor)

    df = rig_fleet.copy()
    df["provider_norm"] = df["provider"].apply(normalize_contractor_name)
    df["owner_norm"] = df["rig_owner"].apply(normalize_contractor_name)

    matches = df[
        (df["provider_norm"] == target) |
        (df["owner_norm"] == target)
    ]

    if matches.empty:
        return None

    hp_values = pd.to_numeric(matches["hp"], errors="coerce").dropna()
    avg_hp = int(round(hp_values.mean())) if not hp_values.empty else "-"

    def yes_rate(column):
        values = matches[column].astype(str).str.upper().str.strip()
        if len(values) == 0:
            return "-"
        return f'{round((values == "YES").mean() * 100)}%'

    return {
        "fleet_size": len(matches),
        "avg_hp": avg_hp,
        "walking": yes_rate("walking"),
        "top_drive": yes_rate("top_drive"),
        "shale_ready": yes_rate("shale_ready"),
    }


def contractor_fleet_html(contractor_info, rig_fleet):
    if contractor_info:
        fleet_info = contractor_fleet_summary(
            contractor_info.get("current_contractor", ""),
            rig_fleet
        )
    else:
        fleet_info = None

    if fleet_info:
        return f"""
          <div class="detail-row"><span>Fleet Size</span><span>{fleet_info.get("fleet_size", "-")}</span></div>
          <div class="detail-row"><span>Average HP</span><span>{fleet_info.get("avg_hp", "-")}</span></div>
          <div class="detail-row"><span>Walking</span><span>{fleet_info.get("walking", "-")}</span></div>
          <div class="detail-row"><span>Top Drive</span><span>{fleet_info.get("top_drive", "-")}</span></div>
          <div class="detail-row"><span>Shale Ready</span><span>{fleet_info.get("shale_ready", "-")}</span></div>
        """

    return """
      <div class="detail-row"><span>Fleet Size</span><span>To verify</span></div>
      <div class="detail-row"><span>Average HP</span><span>-</span></div>
      <div class="detail-row"><span>Walking</span><span>-</span></div>
      <div class="detail-row"><span>Top Drive</span><span>-</span></div>
      <div class="detail-row"><span>Shale Ready</span><span>-</span></div>
    """
