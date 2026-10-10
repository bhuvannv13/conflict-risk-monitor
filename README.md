# Conflict Risk Monitor

[![Tests](https://github.com/bhuvannv13/conflict-risk-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/bhuvannv13/conflict-risk-monitor/actions/workflows/ci.yml)
[![Refresh data and forecast](https://github.com/bhuvannv13/conflict-risk-monitor/actions/workflows/refresh.yml/badge.svg)](https://github.com/bhuvannv13/conflict-risk-monitor/actions/workflows/refresh.yml)

**Live dashboard: https://bhuvannv13.github.io/conflict-risk-monitor/**

An end-to-end data project that estimates, for every country, the probability of **at least 25 state-based battle-related deaths in the next three months**, which is the threshold the Uppsala Conflict Data Program (UCDP) uses for an active armed conflict.

It is built from researcher-coded event data rather than headlines or commentary, retrains itself every month on GitHub Actions, and publishes a static dashboard with a chat assistant that runs entirely in the browser (no API keys, no running costs).

> These are statistical estimates for research and learning. They are not predictions of war and should not be used for decisions about safety or travel.

## What it does

```
UCDP GED (final + monthly candidate) ─┐
                                      ├─> country-month panel ─> features ─> 3 models compared ─> forecast.json ─> dashboard + chat
World Bank indicators (API) ──────────┘        (176 countries,       (time-based split,
                                                1989 to latest)       chosen on validation)
```

| Step | Code | Notes |
|---|---|---|
| Extract | `pipeline/extract.py` | Downloads UCDP GED 26.1 and the newest candidate release it finds on the UCDP downloads page; pages through the World Bank API. Raw files are cached. |
| Transform | `pipeline/transform.py` | Maps Gleditsch-Ward codes to ISO3, builds a zero-filled country-month panel of deaths by violence type. |
| Features | `pipeline/features.py` | Rolling deaths (1, 3, 12, 36 months), events, months since last fatal event, lagged population, GDP per person and infant mortality. Every feature uses only data available at the end of that month. |
| Model | `pipeline/model.py` | Persistence baseline, logistic regression and histogram gradient boosting. Train to 2017, choose on 2018 to 2021, report once on 2022 onwards. |
| Export | `pipeline/export.py` | Writes `docs/data/forecast.json` for the site. |
| Site | `docs/` | Plain HTML, CSS and JavaScript on GitHub Pages: KPI tiles, trend chart, searchable country table, country detail, model card and chat assistant. |

## Results

Filled in from the latest pipeline run (see the model section on the dashboard for the current numbers).

## Run it yourself

```bash
pip install -r requirements.txt
python -m pytest          # unit tests on synthetic data, including a check that features never see the future
python -m pipeline.run    # downloads the data (about 100 MB), trains, writes docs/data/forecast.json
python -m http.server -d docs 8000
```

The `Refresh data and forecast` workflow runs the same steps on the 12th of every month and commits the new `forecast.json`.

## Limitations

- Most of the predictive power comes from recent violence, so the model is much better at saying where violence will continue than where it will start.
- The latest months use UCDP's preliminary candidate data, which can be revised.
- Events are assigned to the month they started; multi-month events are not split.
- Country-level estimates hide where in a country violence happens.

## Data and licences

- **UCDP Georeferenced Event Dataset** and **UCDP Candidate Events Dataset**, CC BY 4.0, https://ucdp.uu.se/downloads/. Cite Sundberg, R. and Melander, E. (2013) "Introducing the UCDP Georeferenced Event Dataset", *Journal of Peace Research* 50(4), and the current UCDP annual article.
- **World Bank World Development Indicators**, CC BY 4.0, https://data.worldbank.org/.
- Code: MIT licence.

## Author

Bhuvann Vinodh Ram · [Portfolio](https://bhuvannv13.github.io/) · [LinkedIn](https://www.linkedin.com/in/bhuvann-vinodh-ram-5545b3210/)
