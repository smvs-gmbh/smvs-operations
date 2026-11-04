from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

PAGE_URL = "https://sai.refdata.ch/download"
MAX_ZIP_BYTES = 64 * 1024 * 1024


class SAIError(ValueError):
    """Fixed, source-value-free SAI integration diagnostic."""


@dataclass(frozen=True)
class Export:
    filename: str
    url: str
    exported_at: datetime  # Filename time; source timezone is not established.


class _Listing(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[tuple[str, list[str]]] = []
        self.parts: list[str] | None = None
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "tr":
            self.parts, self.links = [], []
        if self.parts is not None:
            for name in ("data-url", "href"):
                if values.get(name):
                    self.links.append(values[name])

    def handle_data(self, data):
        if self.parts is not None:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "tr" and self.parts is not None:
            self.rows.append(("".join(self.parts), self.links))
            self.parts = None


def _export_url(value: str) -> str:
    url = urljoin(PAGE_URL, value)
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc.lower() != "sai.refdata.ch"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"/download/structuredexportzip/[0-9]+", parsed.path)
    ):
        raise SAIError("Unexpected SAI export destination.")
    return url


def latest_export(html: str) -> Export:
    listing = _Listing()
    listing.feed(html)
    candidates = set()
    for text, links in listing.rows:
        names = set(re.findall(r"SAI-Export_[0-9]{8}-[0-9]{6}\.zip", text))
        if len(names) != 1:
            continue
        filename = names.pop()
        try:
            timestamp = datetime.strptime(filename, "SAI-Export_%Y%m%d-%H%M%S.zip")  # noqa: DTZ007 - source timezone unknown
        except ValueError:
            continue
        urls = set()
        for link in links:
            if "structuredexportzip" in link.lower():
                urls.add(_export_url(link))
        if len(urls) != 1:
            raise SAIError("Ambiguous SAI export download links.")
        candidates.add(Export(filename, urls.pop(), timestamp))
    if not candidates:
        raise SAIError("No SAI export found in download listing.")
    newest_time = max(item.exported_at for item in candidates)
    newest = [item for item in candidates if item.exported_at == newest_time]
    if len(newest) != 1:
        raise SAIError("Ambiguous latest SAI export.")
    return newest[0]


class SAIClient:
    def __init__(self, client: httpx.Client | None = None):
        self.http = client or httpx.Client(
            timeout=180,
            follow_redirects=False,
            headers={"User-Agent": "SMVS-Operations-SAI/1.0"},
        )
        self._owns_client = client is None

    def close(self):
        if self._owns_client:
            self.http.close()

    def _get(self, url: str, limit: int) -> tuple[bytes, str | None]:
        try:
            with self.http.stream("GET", url, follow_redirects=False) as response:
                if response.status_code != 200:
                    raise SAIError(
                        "SAI download returned an unsuccessful status or redirect."
                    )
                parts, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > limit:
                        raise SAIError("SAI response exceeds size limit.")
                    parts.append(chunk)
                return b"".join(parts), response.headers.get("content-type")
        except httpx.HTTPError:
            raise SAIError("SAI HTTP request failed.") from None

    def discover(self) -> Export:
        content, _ = self._get(PAGE_URL, 4 * 1024 * 1024)
        try:
            return latest_export(content.decode("utf-8-sig"))
        except UnicodeError:
            raise SAIError("SAI listing is not UTF-8.") from None

    def download(self, export: Export) -> tuple[bytes, str | None]:
        return self._get(_export_url(export.url), MAX_ZIP_BYTES)
