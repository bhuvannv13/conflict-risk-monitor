"""Run the whole pipeline:  python -m pipeline.run"""
import json
import logging

import pandas as pd

from . import config, export, extract, features, model, transform


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    log = logging.getLogger("pipeline")

    events, sources = extract.load_events()
    log.info("Loaded %d events (%s to %s)", len(events), events["date_start"].min().date(),
             events["date_start"].max().date())
    end = str(events["date_start"].max().to_period("M"))
    panel = transform.build_panel(events, config.START_MONTH, end)

    try:
        wdi = extract.load_world_bank()
        sources["world_bank"] = {"url": "https://data.worldbank.org/", "indicators": list(config.WDI_INDICATORS)}
    except Exception as error:  # the model still runs on conflict history alone
        log.warning("World Bank download failed, continuing without it: %s", error)
        wdi = pd.DataFrame()

    frame = features.add_features(panel, wdi)
    results, best, periods = model.evaluate(frame)
    log.info("Evaluation: %s", json.dumps(results))
    log.info("Chosen model: %s", best)
    latest, latest_month = model.forecast(frame, best)
    path = export.write(latest, latest_month, panel, results, best, periods, sources)
    log.info("Wrote %s", path)


if __name__ == "__main__":
    main()
