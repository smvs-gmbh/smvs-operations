import threading
import uuid
from contextlib import contextmanager

from app.core.db.session import require_runtime_session
from app.domain.models import SchedulerHeartbeat
from app.integration.artifacts.storage import utcnow


@contextmanager
def worker_heartbeat(factory):
    """An independent thread keeps liveness visible during long report generation."""
    identifier, started, stop = str(uuid.uuid4()), utcnow(), threading.Event()

    def write(status):
        with factory() as s:
            require_runtime_session(s)
            row = s.get(SchedulerHeartbeat, identifier)
            if row is None:
                row = SchedulerHeartbeat(worker_id=identifier, started_at=started)
                s.add(row)
            row.last_seen_at, row.status = utcnow(), status
            s.commit()

    write("running")

    def pulse():
        while not stop.wait(15):
            try:
                write("running")
            except Exception:  # noqa: BLE001, S110 - a stale heartbeat must remain visibly stale, without driver details
                pass

    thread = threading.Thread(target=pulse, daemon=True)
    thread.start()
    try:
        yield identifier
    finally:
        stop.set()
        thread.join(timeout=35)
        try:
            write("stopped")
        except Exception:  # noqa: BLE001, S110
            pass
