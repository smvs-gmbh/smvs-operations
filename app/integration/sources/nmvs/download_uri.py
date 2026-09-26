"""Validate report destinations before obtaining or attaching bearer headers."""
import ipaddress
import re
from urllib.parse import urlsplit

import httpx


class DownloadUriError(ValueError):
    """Fixed diagnostics only; never include source URI values."""


def _https_url(value: str) -> httpx.URL:
    if not isinstance(value, str) or not value or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
        raise DownloadUriError("Malformed download URI")
    if "\\" in value or re.search(r"%(?![0-9A-Fa-f]{2})", value):
        raise DownloadUriError("Malformed download URI")
    try:
        parts = urlsplit(value)
        if parts.scheme.lower() != "https":
            raise DownloadUriError("Download URI requires HTTPS")
        if not parts.netloc or not parts.hostname:
            raise DownloadUriError("Download URI requires an absolute host")
        if "@" in parts.netloc:
            raise DownloadUriError("Download URI userinfo is forbidden")
        if "#" in value:
            raise DownloadUriError("Download URI fragments are forbidden")
        if parts.netloc.endswith(":") or parts.port == 0:
            raise DownloadUriError("Invalid download URI port")
        if "%" in parts.netloc:
            raise DownloadUriError("Invalid download URI host")
        url = httpx.URL(value)
        host = url.raw_host.decode("ascii").lower()
        if ":" in host:
            ipaddress.IPv6Address(host)
        elif not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in host.split(".")):
            raise DownloadUriError("Invalid download URI host")
        if not url.is_absolute_url:
            raise DownloadUriError("Download URI requires an absolute host")
        return url
    except DownloadUriError:
        raise
    except (ValueError, httpx.InvalidURL, UnicodeError):
        raise DownloadUriError("Malformed download URI host or port") from None


def validate_report_base_url(base_url: str) -> httpx.URL:
    url = _https_url(base_url)
    if "?" in base_url:
        raise DownloadUriError("Reporting base URL cannot contain a query")
    return url


def validate_download_uri(uri: str, base_url: str) -> str:
    base = validate_report_base_url(base_url)
    target = _https_url(uri)
    if target.raw_host.lower() != base.raw_host.lower():
        raise DownloadUriError("Unexpected download URI origin")
    if (target.port or 443) != (base.port or 443):
        raise DownloadUriError("Unexpected download URI port")
    return str(target)
