"""Standalone worker process for docker-compose / multi-node deploys."""

import os
import signal
import time

from app.database import Base, engine
from app.worker import start_worker, stop_worker

WORKER_ID = os.getenv("WORKER_ID", "worker-1")


def main():
    Base.metadata.create_all(bind=engine)
    start_worker(WORKER_ID)
    stop = False

    def _handle(_sig, _frm):
        nonlocal stop
        stop = True
        stop_worker()

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)
    while not stop:
        time.sleep(1)


if __name__ == "__main__":
    main()
