"""Sources, versions and modelling choices in one place."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
SITE_DATA_DIR = ROOT / "docs" / "data"

# UCDP Georeferenced Event Dataset (final yearly release) and the monthly candidate release.
# Both are published under CC BY 4.0: https://ucdp.uu.se/downloads/
UCDP_DOWNLOADS_PAGE = "https://ucdp.uu.se/downloads/"
GED_URL = "https://ucdp.uu.se/downloads/ged/ged261-csv.zip"
GED_VERSION = "26.1"
# Used only if the newest candidate file cannot be discovered from the downloads page.
CANDIDATE_FALLBACK_URL = "https://ucdp.uu.se/downloads/candidateged/GEDEvent_v26_0_8.csv"

# World Bank World Development Indicators (CC BY 4.0).
WORLD_BANK_API = "https://api.worldbank.org/v2/country/all/indicator/{indicator}"
WDI_INDICATORS = {
    "SP.POP.TOTL": "population",
    "NY.GDP.PCAP.KD": "gdp_per_capita",
    "SP.DYN.IMRT.IN": "infant_mortality",
}

START_MONTH = "1989-01"

# Target: at least this many state-based battle-related deaths (UCDP's armed-conflict
# threshold) in the next HORIZON months.
TARGET_DEATHS = 25
HORIZON = 3

# Time-based evaluation split (month of the forecast origin).
TRAIN_END = "2017-12"
VALID_END = "2021-12"

RISK_BANDS = [  # lower bound of probability, label
    (0.50, "High"),
    (0.20, "Elevated"),
    (0.05, "Moderate"),
    (0.00, "Low"),
]
