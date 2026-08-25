"""One place to configure logging so every ingest run leaves the same trail."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

from . import config


def setup(name: str) -> logging.Logger:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    logfile = config.LOGS / f"{name}_{stamp}.log"
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s")

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    root.addHandler(stream)

    fileh = logging.FileHandler(logfile)
    fileh.setFormatter(fmt)
    root.addHandler(fileh)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    return logging.getLogger(name)
