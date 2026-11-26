"""TEST-only SMTP capture: retain messages privately, never forward them."""

import asyncio
import os
from pathlib import Path
from uuid import uuid4


def run(directory):
    from aiosmtpd.controller import Controller

    from app.alert_desk.settings import AlertDeskSettings

    settings = AlertDeskSettings()
    if settings.environment != "test" or not settings.alert_desk_test_enabled:
        raise RuntimeError("Capturing SMTP requires explicitly enabled TEST.")
    os.umask(0o077)
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)

    class Capture:
        async def handle_DATA(self, server, session, envelope):
            # No recipient relaying, web UI or message/body logging.
            path = directory / (uuid4().hex + ".eml")
            try:
                with path.open("xb") as stream:
                    stream.write(envelope.original_content)
            except OSError:
                path.unlink(missing_ok=True)
                return "451 Message could not be retained"
            return "250 Captured for TEST only"

    controller = Controller(
        Capture(), hostname="127.0.0.1", port=11025,
        data_size_limit=128 * 1024,
    )
    controller.start()
    try:
        asyncio.run(asyncio.Event().wait())
    finally:
        controller.stop()
