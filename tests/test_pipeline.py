import numpy as np
import pandas as pd

from pipeline import config, extract, features, model, transform
from pipeline.countries import COUNTRIES


def synthetic_events(seed=0, start="2005-01", end="2024-12"):
    """Random events for a handful of countries, with persistent conflict in two of them."""
    rng = np.random.default_rng(seed)
    months = pd.period_range(start, end, freq="M")
    rows = []
    for gw, rate in [(700, 0.9), (520, 0.8), (750, 0.3), (2, 0.02), (205, 0.0)]:
        for month in months:
            if rng.random() < rate:
                day = month.to_timestamp() + pd.Timedelta(days=int(rng.integers(0, 27)))
                rows.append({"country_id": gw, "type_of_violence": int(rng.integers(1, 4)),
                             "date_start": day, "best": int(rng.integers(1, 80))})
    return pd.DataFrame(rows)


def test_country_mapping_is_one_to_one():
    iso3 = [info[0] for info in COUNTRIES.values()]
    assert len(iso3) == len(set(iso3))


def test_latest_candidate_url_picks_newest():
    html = 'a href="candidateged/GEDEvent_v26_0_3.csv" b href="candidateged/GEDEvent_v26_0_12.csv"'
    assert extract.latest_candidate_url(html).endswith("GEDEvent_v26_0_12.csv")
    assert extract.latest_candidate_url("nothing here") is None


def test_panel_is_complete_and_zero_filled():
    events = pd.DataFrame([
        {"country_id": 700, "type_of_violence": 1, "date_start": "2020-03-05", "best": 30},
        {"country_id": 700, "type_of_violence": 3, "date_start": "2020-03-20", "best": 5},
        {"country_id": 99999, "type_of_violence": 1, "date_start": "2020-03-20", "best": 5},
    ])
    panel = transform.build_panel(events, "2020-01", "2020-06")
    assert len(panel) == len(COUNTRIES) * 6
    afg = panel[(panel["iso3"] == "AFG") & (panel["month"] == pd.Period("2020-03", "M"))].iloc[0]
    assert afg["state_based"] == 30 and afg["one_sided"] == 5 and afg["events"] == 2
    assert panel["state_based"].sum() == 30  # unknown country code dropped


def test_target_looks_forward_and_features_do_not():
    panel = transform.build_panel(synthetic_events(), "2005-01", "2024-12")
    frame = features.add_features(panel)
    afg = frame[frame["iso3"] == "AFG"].reset_index(drop=True)
    expected = sum(afg["state_based"].shift(-k) for k in (1, 2, 3)) >= config.TARGET_DEATHS
    labelled = afg["target"].notna()
    assert (afg.loc[labelled, "target"].astype(bool) == expected[labelled]).all()
    assert afg["target"].isna().sum() == config.HORIZON

    # Changing the future must not change features at an earlier month.
    changed = panel.copy()
    future = changed["month"] > pd.Period("2015-06", "M")
    changed.loc[future, ["state_based", "non_state", "one_sided", "events"]] *= 7
    before = frame[frame["month"] <= pd.Period("2015-06", "M")][features.FEATURES[:9]].reset_index(drop=True)
    after_frame = features.add_features(changed)
    after = after_frame[after_frame["month"] <= pd.Period("2015-06", "M")][features.FEATURES[:9]].reset_index(drop=True)
    pd.testing.assert_frame_equal(before, after)


def test_world_bank_values_are_lagged_one_year():
    panel = transform.build_panel(synthetic_events(), "2010-01", "2012-12")
    wdi = pd.DataFrame({"iso3": ["AFG"] * 3, "year": [2009, 2010, 2011],
                        "population": [10.0, 20.0, 30.0], "gdp_per_capita": [1.0, 2.0, 3.0],
                        "infant_mortality": [50.0, 40.0, 30.0]})
    frame = features.add_features(panel, wdi)
    afg = frame[frame["iso3"] == "AFG"].set_index("month")
    assert afg.loc[pd.Period("2011-05", "M"), "infant_mortality"] == 40.0
    assert afg.loc[pd.Period("2012-05", "M"), "infant_mortality"] == 30.0


def test_evaluate_and_forecast_on_synthetic_data():
    panel = transform.build_panel(synthetic_events(), "2005-01", "2024-12")
    frame = features.add_features(panel)
    results, best, periods = model.evaluate(frame)
    assert best in ("logistic_regression", "gradient_boosting")
    assert set(results) == {"persistence", "logistic_regression", "gradient_boosting"}
    latest, month = model.forecast(frame, best)
    assert month == pd.Period("2024-12", "M")
    assert len(latest) == len(COUNTRIES)
    assert latest["probability"].between(0, 1).all()
    assert set(latest["band"]) <= {label for _, label in config.RISK_BANDS}
    # A country with persistent conflict should rank above a country with none.
    probability = latest.set_index("iso3")["probability"]
    assert probability["AFG"] > probability["IRL"]


def test_risk_band_thresholds():
    assert model.risk_band(0.7) == "High"
    assert model.risk_band(0.3) == "Elevated"
    assert model.risk_band(0.1) == "Moderate"
    assert model.risk_band(0.01) == "Low"


def test_export_writes_site_json(tmp_path=None):
    import json
    import tempfile
    from pathlib import Path

    from pipeline import export

    out = Path(tmp_path or tempfile.mkdtemp())
    panel = transform.build_panel(synthetic_events(), "2005-01", "2024-12")
    frame = features.add_features(panel)
    results, best, periods = model.evaluate(frame)
    latest, month = model.forecast(frame, best)
    path = export.write(latest, month, panel, results, best, periods, {"test": {}}, out_dir=out)
    data = json.loads(path.read_text())
    assert data["data_through"] == "2024-12"
    assert len(data["countries"]) == len(COUNTRIES)
    assert len(data["trend_months"]) == export.TREND_MONTHS
    afg = next(c for c in data["countries"] if c["iso3"] == "AFG")
    assert len(afg["trend_state_based"]) == export.TREND_MONTHS
    assert len(data["global"]["months"]) == 120
