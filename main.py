"""
AMRIT Research OS v3.0 - Autonomous Scientific Discovery Engine
Entry point.
"""

import logging
import yaml

logging.basicConfig(
    filename="logs/system.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def main():
    config = load_config()
    logger.info("AMRIT Research OS v3.0 started with config: %s", config)
    print("AMRIT Research OS v3.0 — Autonomous Scientific Discovery Engine")


if __name__ == "__main__":
    main()
