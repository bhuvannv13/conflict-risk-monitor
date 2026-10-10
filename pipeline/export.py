"""Write the JSON files the website reads."""
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import config

TREND_MONTHS = 24


def _round(value, digits=4):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return round(float(value), digits)


def country_records(latest, panel):
    panel = panel.sort_values("month")
    end = latest["month"].iloc[0]
    start = end - (TREND_MONTHS - 1)
    recent = panel[(panel["month"] >= start) & (panel["month"] <= end)]
    trends = {gw: g for gw, g in recent.groupby("gw")}
    records = []
    for row in latest.itertuples():
        g = trends.get(row.gw)
        last12 = g[g["month"] > end - 12] if g is not None else None
        records.append({
            "iso3": row.iso3, "name": row.country, "region": row.region,
            "probability": _round(row.probability), "band": row.band,
            "deaths_12m": {
                "state_based": int(round(last12["state_based"].sum())) if last12 is not None else 0,
                "non_state": int(round(last12["non_state"].sum())) if last12 is not None else 0,
                "one_sided": int(round(last12["one_sided"].sum())) if last12 is not None else 0,
            },
            "events_12m": int(round(last12["events"].sum())) if last12 is not None else 0,
            "months_since_fatal": int(row.months_since_fatal),
            "trend_state_based": [int(round(v)) for v in g["state_based"]] if g is not None else [],
            "gdp_per_capita": _round(np.exp(row.log_gdp_per_capita), 0) if pd.notna(row.log_gdp_per_capita) else None,
            "infant_mortality": _round(row.infant_mortality, 1),
        })
    return records


def global_series(panel):
    by_month = panel.groupby("month")[["state_based", "non_state", "one_sided"]].sum()
    by_month = by_month[by_month.index >= by_month.index.max() - 119]
    return {
        "months": [str(m) for m in by_month.index],
        "state_based": [int(round(v)) for v in by_month["state_based"]],
        "non_state": [int(round(v)) for v in by_month["non_state"]],
        "one_sided": [int(round(v)) for v in by_month["one_sided"]],
    }


def write(latest, latest_month, panel, results, best, periods, sources, out_dir=config.SITE_DATA_DIR):
    out_dir.mkdir(parents=True, exist_ok=True)
    trend_end = latest_month
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "data_through": str(latest_month),
        "trend_months": [str(trend_end - (TREND_MONTHS - 1 - i)) for i in range(TREND_MONTHS)],
        "target": {
            "deaths": config.TARGET_DEATHS, "horizon_months": config.HORIZON,
            "description": (f"Probability of at least {config.TARGET_DEATHS} state-based battle-related "
                            f"deaths in the {config.HORIZON} months after {latest_month}"),
        },
        "model": {"chosen": best, "metrics": results, "periods": periods},
        "bands": [{"min": lower, "label": label} for lower, label in config.RISK_BANDS],
        "sources": sources,
        "countries": country_records(latest, panel),
        "global": global_series(panel),
    }
    path = out_dir / "forecast.json"
    path.write_text(json.dumps(payload, separators=(",", ":")))
    return path
