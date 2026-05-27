from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logging(service_name: str = "solver", level: int = logging.DEBUG) -> logging.Logger:
    log_dir = Path("/app/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s")

    logger = logging.getLogger(service_name)
    if not logger.handlers:
        fh = logging.FileHandler(log_dir / f"{service_name}.log")
        fh.setFormatter(fmt)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(sh)

    logger.setLevel(level)
    return logger


logger = setup_logging("solver")
