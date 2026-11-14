import asyncio
import logging
import signal
from pathlib import Path

from app.core.config import get_settings
from app.core.database import engine
from worker.processor import reclaim_stale, run_once

log = logging.getLogger("worker")

HEARTBEAT_FILE = Path("/tmp/worker-alive")  # его проверяет healthcheck контейнера
RECLAIM_EVERY = 60.0


async def _alive_loop() -> None:
    while True:
        HEARTBEAT_FILE.touch()
        await asyncio.sleep(10)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    loop = asyncio.get_running_loop()
    stopping = asyncio.Event()
    current: asyncio.Task | None = None

    def on_signal() -> None:
        stopping.set()
        if current is not None and not current.done():
            current.cancel()  # run_once вернёт задачу в очередь

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, on_signal)

    alive = asyncio.create_task(_alive_loop())
    log.info("worker started")
    next_reclaim = 0.0
    try:
        while not stopping.is_set():
            if loop.time() >= next_reclaim:
                try:
                    await reclaim_stale()
                except Exception:
                    log.exception("reclaim_stale failed")
                next_reclaim = loop.time() + RECLAIM_EVERY

            current = asyncio.create_task(run_once())
            try:
                worked = await current
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("worker iteration failed")
                worked = False

            if not worked:
                try:
                    await asyncio.wait_for(stopping.wait(), timeout=settings.worker_poll_seconds)
                except TimeoutError:
                    pass
    finally:
        alive.cancel()
        await engine.dispose()
        log.info("worker stopped")


if __name__ == "__main__":
    asyncio.run(main())