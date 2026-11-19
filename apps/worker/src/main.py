"""Reaboard Worker Daemon Entrypoint."""

import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [worker] %(name)s: %(message)s",
)

logger = logging.getLogger("reaboard.worker.daemon")


def main() -> None:
    logger.info("Initializing Reaboard sandboxed worker daemon...")
    # In container, invokes `arq apps.worker.src.runner.WorkerSettings`
    print("Reaboard worker initialized in single-job isolation mode.")


if __name__ == "__main__":
    main()
