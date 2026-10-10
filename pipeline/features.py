"""Features known at the end of each month, and the forward-looking target."""
import numpy as np
import pandas as pd

from . import config

FEATURES = [
    "sb_1m", "sb_3m", "sb_12m", "sb_36m", "ns_12m", "os_12m", "events_12m",
    "months_since_fatal", "months_since_sb25", "log_population", "log_gdp_per_capita",
    "infant_mortality",
]


def _rolling(group, column, window):
    return np.log1p(group[column].rolling(window, min_periods=1).sum())


def _months_since(flag):
    """Months since flag was last true (0 if true this month), capped at 240."""
    out, counter = [], 240
    for value in flag:
        counter = 0 if value else min(counter + 1, 240)
        out.append(counter)
    return out


def add_features(panel, wdi=None):
    """Return panel with FEATURES and the target columns added.

    Every feature for month t uses data up to and including t only. The target uses
    months t+1 .. t+HORIZON and is NaN where those months are not yet observed.
    """
    panel = panel.sort_values(["gw", "month"]).copy()
    parts = []
    for _, group in panel.groupby("gw", sort=False):
        group = group.copy()
        group["sb_1m"] = np.log1p(group["state_based"])
        group["sb_3m"] = _rolling(group, "state_based", 3)
        group["sb_12m"] = _rolling(group, "state_based", 12)
        group["sb_36m"] = _rolling(group, "state_based", 36)
        group["ns_12m"] = _rolling(group, "non_state", 12)
        group["os_12m"] = _rolling(group, "one_sided", 12)
        group["events_12m"] = np.log1p(group["events"].rolling(12, min_periods=1).sum())
        total = group["state_based"] + group["non_state"] + group["one_sided"]
        group["months_since_fatal"] = _months_since(total > 0)
        group["months_since_sb25"] = _months_since(group["state_based"] >= config.TARGET_DEATHS)

        future = sum(group["state_based"].shift(-k) for k in range(1, config.HORIZON + 1))
        group["future_sb"] = future
        group["target"] = np.where(future.isna(), np.nan, (future >= config.TARGET_DEATHS).astype(float))
        parts.append(group)
    panel = pd.concat(parts)

    panel["year"] = panel["month"].dt.year
    if wdi is not None and len(wdi):
        panel = _join_wdi(panel, wdi)
    for column in ["log_population", "log_gdp_per_capita", "infant_mortality"]:
        if column not in panel:
            panel[column] = np.nan
    return panel.drop(columns=["year"])


def _join_wdi(panel, wdi):
    """Join last year's World Bank values (carried forward when the latest years are missing)."""
    wdi = wdi.copy()
    wdi["log_population"] = np.log(wdi["population"]) if "population" in wdi else np.nan
    wdi["log_gdp_per_capita"] = np.log(wdi["gdp_per_capita"]) if "gdp_per_capita" in wdi else np.nan
    if "infant_mortality" not in wdi:
        wdi["infant_mortality"] = np.nan
    wdi = wdi[["iso3", "year", "log_population", "log_gdp_per_capita", "infant_mortality"]]

    years = range(int(panel["year"].min()) - 1, int(panel["year"].max()) + 1)
    grid = pd.MultiIndex.from_product([panel["iso3"].unique(), years], names=["iso3", "year"])
    wdi = wdi.set_index(["iso3", "year"]).reindex(grid).groupby(level="iso3").ffill().reset_index()
    wdi["year"] = wdi["year"] + 1  # values for year Y are used from Y+1
    return panel.merge(wdi, on=["iso3", "year"], how="left")
