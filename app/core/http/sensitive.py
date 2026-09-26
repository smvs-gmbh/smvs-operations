"""Context-local suppression of transport diagnostics for credentialed requests."""
import logging
from contextlib import contextmanager
from contextvars import ContextVar

_sensitive_request = ContextVar("sensitive_http_request", default=False)


class _SensitiveRequestFilter(logging.Filter):
    def filter(self, record):
        return not _sensitive_request.get()


_filter = _SensitiveRequestFilter()


@contextmanager
def sensitive_http_request():
    # HTTPX logs URLs; httpcore DEBUG logs can include request/response headers.
    # Filters remain installed but only suppress this execution context.
    names = {"httpx", "httpcore", "httpcore.connection", "httpcore.connection_pool",
             "httpcore.http11", "httpcore.http2", "httpcore.proxy", "httpcore.socks"}
    names.update(name for name in list(logging.Logger.manager.loggerDict) if name.startswith("httpcore."))
    for name in names:
        logging.getLogger(name).addFilter(_filter)
    token = _sensitive_request.set(True)
    try:
        yield
    finally:
        _sensitive_request.reset(token)
