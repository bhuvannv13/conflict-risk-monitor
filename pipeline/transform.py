"""Turn raw events into a complete country-month panel."""
import logging

import pandas as pd

from .countries import COUNTRIES

log = logging.getLogger(__name__)
VIOLENCE_TYPES = {1: "state_based", 2: "non_state", 3: "one_sided"}


def spread_over_months(events):
    """One row per event and calendar month it covers, with deaths split evenly across those months.

    Some UCDP events summarise fighting over many months (for example a year-long estimate).
    Assigning all of those deaths to the first month creates false spikes, so they are spread.
    The event itself is counted once, in its first month (column "first").
    """
    events = events.copy()
    events["best"] = pd.to_numeric(events["best"], errors="coerce").fillna(0)
    start = pd.to_datetime(events["date_start"]).dt.to_period("M")
    end_raw = pd.to_datetime(events["date_end"]) if "date_end" in events else pd.to_datetime(events["date_start"])
    end = end_raw.fillna(pd.to_datetime(events["date_start"])).dt.to_period("M")
    end = end.where(end >= start, start)
    span = (end.dt.year - start.dt.year) * 12 + (end.dt.month - start.dt.month) + 1
    events["_start"], events["_span"] = start, span
    single = events[span == 1].assign(month=start[span == 1], first=True)
    multi = events[span > 1]
    rows = [single]
    if len(multi):
        expanded = multi.loc[multi.index.repeat(multi["_span"])].copy()
        offset = expanded.groupby(level=0).cumcount()
        expanded["month"] = [s + int(o) for s, o in zip(expanded["_start"], offset)]
        expanded["best"] = expanded["best"] / expanded["_span"]
        expanded["first"] = offset.values == 0
        rows.append(expanded)
    return pd.concat(rows, ignore_index=True).drop(columns=["_start", "_span"])


def build_panel(events, start, end):
    """One row per country and month from start to end (inclusive), zero-filled.

    Deaths from events lasting several months are split evenly across those months. Columns: gw, iso3, country,
    region, month, state_based, non_state, one_sided (best-estimate deaths) and events.
    """
    events = events.copy()
    events["country_id"] = pd.to_numeric(events["country_id"], errors="coerce")
    unknown = sorted(set(events["country_id"].dropna().astype(int)) - set(COUNTRIES))
    if unknown:
        log.warning("Dropping events for country codes not in the mapping: %s", unknown)
    events = events[events["country_id"].isin(list(COUNTRIES))]
    events = spread_over_months(events)
    events = events[(events["month"] >= pd.Period(start, "M")) & (events["month"] <= pd.Period(end, "M"))]
    events["kind"] = events["type_of_violence"].map(VIOLENCE_TYPES)

    deaths = events.pivot_table(index=["country_id", "month"], columns="kind", values="best",
                                aggfunc="sum", fill_value=0)
    counts = events[events["first"]].groupby(["country_id", "month"]).size().rename("events")

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
