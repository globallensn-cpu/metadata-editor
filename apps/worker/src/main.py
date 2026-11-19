"""Reaboard Worker Daemon Entrypoint."""

import logging

from arq import run_worker

from apps.worker.src.runner import WorkerSettings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [worker] %(name)s: %(message)s",
)

logger = logging.getLogger("reaboard.worker.daemon")


def main() -> None:
    logger.info("Initializing Reaboard ARQ sandboxed worker daemon...")
    run_worker(WorkerSettings)


if __name__ == "__main__":
    main()
