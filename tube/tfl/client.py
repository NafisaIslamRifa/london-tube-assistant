"""A small, testable client for the TfL Unified API.

Everything that talks to the network goes through `TflClient.get_json`, so tests can
swap in a fake session and never touch the internet.
"""

from __future__ import annotations

import time
from typing import Any

import requests

from tube import config


class TflError(RuntimeError):
    """The TfL API could not be reached or returned an error."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


RETRY_STATUSES = {429, 500, 502, 503, 504}


class TflClient:
    def __init__(self, base_url: str = config.TFL_BASE_URL, app_key: str = config.TFL_APP_KEY,
                 session: Any | None = None, timeout: float = config.TFL_TIMEOUT,
                 retries: int = 1, sleep=time.sleep):
        self.base_url = base_url.rstrip("/")
        self.app_key = app_key
        self.session = session or requests.Session()
        self.timeout = timeout
        self.retries = retries
        self._sleep = sleep

    def get_json(self, path: str, params: dict | None = None) -> Any:
        """GET base_url + path and return parsed JSON. Retries briefly on 429/5xx."""
        params = dict(params or {})
        if self.app_key:
            params["app_key"] = self.app_key
        url = f"{self.base_url}/{path.lstrip('/')}"

        for attempt in range(self.retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                if attempt < self.retries:
                    self._sleep(1.0)
                    continue
                raise TflError(f"Could not reach TfL: {exc}") from exc

            if resp.status_code in RETRY_STATUSES and attempt < self.retries:
                self._sleep(2.0 if resp.status_code == 429 else 1.0)
                continue
            if resp.status_code >= 400:
                raise TflError(f"TfL returned HTTP {resp.status_code} for {path}",
                               status=resp.status_code)
            try:
                return resp.json()
            except ValueError as exc:
                raise TflError(f"TfL returned a non-JSON reply for {path}") from exc

        raise TflError(f"TfL request failed for {path}")  # pragma: no cover
