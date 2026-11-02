# Power BI report

The monthly pipeline writes flat CSV tables to [`powerbi/data`](data). The Power Query script in this folder reads them straight from GitHub, so the report refreshes itself when the data does.

| Table | Rows | What it holds |
|---|---|---|
| `dim_country` | one per country | Name, region and latest World Bank indicators |
| `fact_forecast` | one per country | Latest probability, last month's probability, change, risk band, rank |
| `fact_country_month` | country x month since 2000 | Deaths by violence type, events |
| `fact_backtest` | country x month, test period | Out-of-sample probability, persistence baseline and what actually happened |
| `fact_model_metrics` | model x period | ROC AUC, average precision, Brier score |
| `fact_feature_importance` | one per model input | Permutation importance of the chosen model |
| `meta` | one | Data-through month, model, UCDP versions |

## Build the report (about 15 minutes)

1. In Power BI Desktop, add a text **parameter** named `BaseUrl` with the URL at the top of [`queries.pq`](queries.pq).
2. Create one **Blank Query** per `// ---- Query: ... ----` block in `queries.pq` (Advanced Editor), named exactly as in the heading. Load `dim_date` too.
3. In **Model view**, create the relationships listed at the top of [`measures.dax`](measures.dax).
4. Add the measures from `measures.dax` to a new `_Measures` table. Create the `Alert threshold` what-if parameter and the `Probability bucket` column described in the file.
5. **View > Themes > Browse for themes** and pick [`theme.json`](theme.json).
6. Suggested pages:
   - **Overview**: cards for `High Risk Countries`, `Elevated Risk Countries`, `Countries Rising`, `Data Through`; filled map on `dim_country[country]` coloured by `Risk Band Colour`; top 15 table by `risk_rank`.
   - **Country**: slicer on `dim_country[country]`; stacked column of the three death measures by month; cards for `Risk Probability` and `Change vs Last Month (pts)`.
   - **Model check**: line chart of `Backtest Predicted Rate` and `Backtest Actual Rate` by `Probability bucket` (a well-calibrated model follows the diagonal); `Alert Precision` and `Alert Recall` with the threshold slicer; table from `fact_model_metrics`.
   - **Drivers**: bar chart of `fact_feature_importance`.

## Refresh

- **Power BI Service**: publish, then set a scheduled refresh in the dataset settings. The source is a public URL, so no gateway is needed. The data changes once a month (the workflow runs on the 12th).
- **Local clone instead of GitHub**: change the parameter to your folder and replace `Web.Contents(BaseUrl & "x.csv")` with `File.Contents(BaseUrl & "x.csv")` in each query.

The same caveat as the dashboard applies: these are statistical estimates for research and learning, not predictions of war.
