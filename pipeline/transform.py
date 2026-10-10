"""Turn raw events into a complete country-month panel."""
import logging

import pandas as pd

from .countries import COUNTRIES

log = logging.getLogger(__name__)
VIOLENCE_TYPES = {1: "state_based", 2: "non_state", 3: "one_sided"}


def build_panel(events, start, end):
    """One row per country and month from start to end (inclusive), zero-filled.

    Events are assigned to the month in which they started. Columns: gw, iso3, country,
    region, month, state_based, non_state, one_sided (best-estimate deaths) and events.
    """
    events = events.copy()
    events["country_id"] = pd.to_numeric(events["country_id"], errors="coerce")
    unknown = sorted(set(events["country_id"].dropna().astype(int)) - set(COUNTRIES))
    if unknown:
        log.warning("Dropping events for country codes not in the mapping: %s", unknown)
    events = events[events["country_id"].isin(list(COUNTRIES))]
    events["month"] = pd.to_datetime(events["date_start"]).dt.to_period("M")
    events = events[(events["month"] >= pd.Period(start, "M")) & (events["month"] <= pd.Period(end, "M"))]
    events["kind"] = events["type_of_violence"].map(VIOLENCE_TYPES)
    events["best"] = pd.to_numeric(events["best"], errors="coerce").fillna(0)

    deaths = events.pivot_table(index=["country_id", "month"], columns="kind", values="best",
                                aggfunc="sum", fill_value=0)
    counts = events.groupby(["country_id", "month"]).size().rename("events")

    months = pd.period_range(start, end, freq="M")
    index = pd.MultiIndex.from_product([sorted(COUNTRIES), months], names=["country_id", "month"])
    panel = pd.DataFrame(index=index).join(deaths).join(counts)
    for column in list(VIOLENCE_TYPES.values()) + ["events"]:
        if column not in panel:
            panel[column] = 0
        panel[column] = panel[column].fillna(0)
    panel = panel.reset_index().rename(columns={"country_id": "gw"})
    meta = pd.DataFrame([(gw, *info) for gw, info in COUNTRIES.items()],
                        columns=["gw", "iso3", "country", "region"])
    return panel.merge(meta, on="gw")[
        ["gw", "iso3", "country", "region", "month", "state_based", "non_state", "one_sided", "events"]
    ]
