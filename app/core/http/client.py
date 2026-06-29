from collections.abc import Mapping
from pathlib import Path

import httpx


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

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
