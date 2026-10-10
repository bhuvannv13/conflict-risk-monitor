"""Download raw data. Files are cached in data/raw so reruns are cheap."""
import io
import re
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

from . import config

GED_COLUMNS = ["country_id", "type_of_violence", "date_start", "best"]
HEADERS = {"User-Agent": "conflict-risk-monitor (github.com/bhuvannv13/conflict-risk-monitor)"}


def download(url, dest, retries=3):
    """Download url to dest unless it is already cached."""
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, headers=HEADERS, stream=True, timeout=120) as response:
                response.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as handle:
                    for chunk in response.iter_content(1 << 20):
                        handle.write(chunk)
                tmp.rename(dest)
                return dest
        except requests.RequestException:
            if attempt == retries:
                raise
            time.sleep(5 * attempt)
    return dest


def latest_candidate_url(page_html):
    """Return the URL of the newest monthly candidate events file listed on the downloads page."""
    found = re.findall(r"candidateged/GEDEvent_v(\d+)_0_(\d+)\.csv", page_html)
    if not found:
        return None
    major, minor = max(found, key=lambda pair: (int(pair[0]), int(pair[1])))
    return f"https://ucdp.uu.se/downloads/candidateged/GEDEvent_v{major}_0_{minor}.csv"


def discover_candidate_url():
    try:
        page = requests.get(config.UCDP_DOWNLOADS_PAGE, headers=HEADERS, timeout=60).text
        return latest_candidate_url(page) or config.CANDIDATE_FALLBACK_URL
    except requests.RequestException:
        return config.CANDIDATE_FALLBACK_URL


def read_ged_csv(handle):
    """Read the columns we need from a GED-format CSV (final or candidate)."""
    frame = pd.read_csv(handle, usecols=lambda c: c.lower() in GED_COLUMNS, low_memory=False)
    frame.columns = [c.lower() for c in frame.columns]
    return frame


def load_ged(path):
    with zipfile.ZipFile(path) as archive:
        name = next(n for n in archive.namelist() if n.lower().endswith(".csv"))
        with archive.open(name) as handle:
            return read_ged_csv(io.TextIOWrapper(handle, encoding="utf-8"))


def load_events():
    """Final GED plus the newest candidate events that fall after the final release."""
    ged = load_ged(download(config.GED_URL, config.RAW_DIR / Path(config.GED_URL).name))
    candidate_url = discover_candidate_url()
    candidate = read_ged_csv(download(candidate_url, config.RAW_DIR / Path(candidate_url).name))
    ged["date_start"] = pd.to_datetime(ged["date_start"], errors="coerce")
    candidate["date_start"] = pd.to_datetime(candidate["date_start"], errors="coerce")
    candidate = candidate[candidate["date_start"] > ged["date_start"].max()]
    events = pd.concat([ged, candidate], ignore_index=True).dropna(subset=["date_start"])
    sources = {
        "ged": {"url": config.GED_URL, "version": config.GED_VERSION},
        "candidate": {"url": candidate_url, "version": re.sub(r".*_v(\d+)_0_(\d+)\.csv", r"\1.0.\2", candidate_url)},
    }
    return events, sources


def fetch_world_bank(indicator):
    """Fetch every country-year value for one indicator."""
    url = config.WORLD_BANK_API.format(indicator=indicator)
    rows, page = [], 1
    while True:
        response = requests.get(
            url, params={"format": "json", "per_page": 20000, "page": page, "date": "1985:2030"},
            headers=HEADERS, timeout=120,
        )
        response.raise_for_status()
        meta, data = response.json()
        for item in data or []:
            if item.get("value") is not None and item.get("countryiso3code"):
                rows.append((item["countryiso3code"], int(item["date"]), float(item["value"])))
        if page >= int(meta.get("pages", 1)):
            break
        page += 1
    return pd.DataFrame(rows, columns=["iso3", "year", "value"])


def load_world_bank():
    frames = []
    for indicator, name in config.WDI_INDICATORS.items():
        cache = config.RAW_DIR / f"wdi_{indicator}.csv"
        if cache.exists():
            frame = pd.read_csv(cache)
        else:
            frame = fetch_world_bank(indicator)
            cache.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(cache, index=False)
        frames.append(frame.assign(indicator=name))
    wide = pd.concat(frames).pivot_table(index=["iso3", "year"], columns="indicator", values="value")
    return wide.reset_index()
