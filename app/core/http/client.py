from collections.abc import Mapping
from pathlib import Path
from typing import Self

import httpx

from app.core.http.sensitive import sensitive_http_request


class SensitiveHttpError(RuntimeError):
    """Sanitized transport failure for requests containing secrets."""


class HttpClient:
    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self._client = httpx.Client(timeout=timeout_seconds)

    def get(
        self,
        url: str,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        response = self._client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response

    def get_sensitive(self, url: str, headers: Mapping[str, str],
                      params: Mapping[str, str] | None = None) -> httpx.Response:
        # Caller validates the destination first. Never follow even same-origin
        # redirects; callers handle status codes without exposing response URLs.
        with sensitive_http_request():
            try:
                return self._client.get(url, headers=headers, params=params, follow_redirects=False)
            except httpx.HTTPError:
                raise SensitiveHttpError("Authenticated HTTP request failed") from None

    def post(
        self,
        url: str,
        headers: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
        json: object | None = None,
    ) -> httpx.Response:
        response = self._client.post(url, headers=headers, data=data, json=json)
        response.raise_for_status()
        return response

    def download(
        self,
        url: str,
        target_path: Path,
        headers: Mapping[str, str] | None = None,
    ) -> Path:
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with self._client.stream("GET", url, headers=headers) as response:
            response.raise_for_status()
            with target_path.open("wb") as file:
                for chunk in response.iter_bytes():
                    file.write(chunk)

        return target_path

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
