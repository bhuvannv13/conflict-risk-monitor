"""Write flat CSV tables for Power BI (star schema: one dimension, several fact tables).

Files are written to powerbi/data and committed by the monthly workflow, so the Power Query
script in powerbi/ can read them straight from GitHub and refresh on a schedule.
"""
import numpy as np
import pandas as pd

from . import config

def _month_start(period_series):
    return period_series.dt.to_timestamp().dt.strftime("%Y-%m-%d")


def dim_country(latest):
    """One row per country with the latest risk, band and development indicators."""
    out = latest[["iso3", "country", "region"]].copy()
    out["gdp_per_capita"] = np.exp(latest["log_gdp_per_capita"]).round(0)
    out["net_migration"] = (np.sign(latest["net_migration_slog"]) * np.expm1(latest["net_migration_slog"].abs())).round(0)
    out["population"] = np.exp(latest["log_population"]).round(0)
    for column in ["infant_mortality", "inflation", "youth_unemployment", "military_spend",
                   "secondary_enrolment", "urban_share"]:
        out[column] = latest[column].round(2)
    return out.sort_values("iso3").reset_index(drop=True)


def fact_forecast(latest, latest_month):
    out = latest[["iso3", "probability", "probability_prev", "change_1m", "band", "months_since_fatal"]].copy()
    out["forecast_origin"] = _month_start(pd.Series([latest_month] * len(out), index=out.index))
    out["target_deaths"] = config.TARGET_DEATHS
    out["horizon_months"] = config.HORIZON
    out["risk_rank"] = out["probability"].rank(ascending=False, method="first").astype(int)
    for column in ["probability", "probability_prev", "change_1m"]:
        out[column] = out[column].round(4)
    return out.sort_values("risk_rank").reset_index(drop=True)


def fact_country_month(panel):
    out = panel[panel["month"] >= pd.Period(config.POWERBI_FROM, "M")][
        ["iso3", "month", "state_based", "non_state", "one_sided", "events"]].copy()
    out["month"] = _month_start(out["month"])
    for column in ["state_based", "non_state", "one_sided"]:
        out[column] = out[column].round(1)
    out["total_deaths"] = out[["state_based", "non_state", "one_sided"]].sum(axis=1).round(1)
    return out.reset_index(drop=True)


def fact_backtest(backtest):
    out = backtest[["iso3", "month", "probability", "persistence", "target", "future_sb"]].copy()
    out["month"] = _month_start(out["month"])
    out["probability"] = out["probability"].round(4)
    out["persistence"] = out["persistence"].round(4)
    out["future_sb"] = out["future_sb"].round(1)
    out["target"] = out["target"].astype(int)
    return out.reset_index(drop=True)


def fact_model_metrics(results, best):
    rows = []
    for model_name, by_period in results.items():
        for period, m in by_period.items():
            rows.append({"model": model_name, "period": period, "chosen": model_name == best, **m})
    return pd.DataFrame(rows)


def write(latest, latest_month, panel, backtest, results, best, importance, sources, out_dir=config.POWERBI_DIR):
    out_dir.mkdir(parents=True, exist_ok=True)
    tables = {
        "dim_country": dim_country(latest),
        "fact_forecast": fact_forecast(latest, latest_month),
        "fact_country_month": fact_country_month(panel),
        "fact_backtest": fact_backtest(backtest),
        "fact_model_metrics": fact_model_metrics(results, best),
        "fact_feature_importance": pd.DataFrame(importance),
        "meta": pd.DataFrame([{
            "data_through": str(latest_month), "generated_at": pd.Timestamp.now("UTC").strftime("%Y-%m-%d %H:%M"),
            "chosen_model": best, "ged_version": sources.get("ged", {}).get("version", ""),
            "candidate_releases": sources.get("candidate", {}).get("version", ""),
        }]),
    }
    paths = []
    for name, table in tables.items():
        path = out_dir / f"{name}.csv"
        table.to_csv(path, index=False)
        paths.append(path)
    return paths
