from __future__ import annotations

import logging


def configure_logging(level: str) -> None:
    """Configure application logging once per process."""

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
