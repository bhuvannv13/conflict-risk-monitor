// Conflict Risk Monitor: Power Query (M) queries.
// In Power BI Desktop: Home > Transform data > New Source > Blank Query > Advanced Editor,
// paste ONE block below per query, and name the query exactly as in its heading.
// To work from a local clone instead of GitHub, see the README.

// ---- Parameter: BaseUrl (Manage Parameters > New Parameter, Type Text) ----
"https://raw.githubusercontent.com/bhuvannv13/conflict-risk-monitor/Bhuvann13/powerbi/data/"

// ---- Query: dim_country ----
let
    Source = Csv.Document(Web.Contents(BaseUrl & "dim_country.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"iso3", type text}, {"country", type text}, {"region", type text},
        {"gdp_per_capita", type number}, {"net_migration", type number}, {"population", type number},
        {"infant_mortality", type number}, {"inflation", type number}, {"youth_unemployment", type number},
        {"military_spend", type number}, {"secondary_enrolment", type number}, {"urban_share", type number}}, "en-US")
in
    Typed

// ---- Query: fact_forecast ----
let
    Source = Csv.Document(Web.Contents(BaseUrl & "fact_forecast.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"iso3", type text}, {"probability", type number}, {"probability_prev", type number}, {"change_1m", type number},
        {"band", type text}, {"months_since_fatal", Int64.Type}, {"forecast_origin", type date},
        {"target_deaths", Int64.Type}, {"horizon_months", Int64.Type}, {"risk_rank", Int64.Type}}, "en-US")
in
    Typed

// ---- Query: fact_country_month ----
let
    Source = Csv.Document(Web.Contents(BaseUrl & "fact_country_month.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"iso3", type text}, {"month", type date}, {"state_based", type number}, {"non_state", type number},
        {"one_sided", type number}, {"events", Int64.Type}, {"total_deaths", type number}}, "en-US")
in
    Typed

// ---- Query: fact_backtest ----
let
    Source = Csv.Document(Web.Contents(BaseUrl & "fact_backtest.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"iso3", type text}, {"month", type date}, {"probability", type number}, {"persistence", type number},
        {"target", Int64.Type}, {"future_sb", type number}}, "en-US")
in
    Typed

// ---- Query: fact_model_metrics ----
let
    Source = Csv.Document(Web.Contents(BaseUrl & "fact_model_metrics.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"model", type text}, {"period", type text}, {"chosen", type logical}, {"roc_auc", type number},
        {"average_precision", type number}, {"brier", type number}, {"n", Int64.Type}, {"positives", Int64.Type}}, "en-US")
in
    Typed

// ---- Query: fact_feature_importance ----
let
    Source = Csv.Document(Web.Contents(BaseUrl & "fact_feature_importance.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"feature", type text}, {"importance", type number}}, "en-US")
in
    Typed

// ---- Query: meta ----
let
    Source = Csv.Document(Web.Contents(BaseUrl & "meta.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
in
    Promoted

// ---- Query: dim_date (one row per month, for the time axis) ----
let
    First = Date.StartOfMonth(List.Min(fact_country_month[month])),
    Last = Date.StartOfMonth(List.Max(fact_country_month[month])),
    Count = (Date.Year(Last) - Date.Year(First)) * 12 + Date.Month(Last) - Date.Month(First) + 1,
    Months = List.Transform({0 .. Count - 1}, each Date.AddMonths(First, _)),
    AsTable = Table.FromList(Months, Splitter.SplitByNothing(), {"Date"}),
    Typed = Table.TransformColumnTypes(AsTable, {{"Date", type date}}),
    WithYear = Table.AddColumn(Typed, "Year", each Date.Year([Date]), Int64.Type),
    WithLabel = Table.AddColumn(WithYear, "Month label", each Date.ToText([Date], "MMM yyyy"), type text)
in
    WithLabel
