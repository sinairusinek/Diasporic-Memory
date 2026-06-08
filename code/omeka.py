"""Thin client for the Omeka S REST API.

Credentials are read from ../.env (OMEKA_BASE_URL, OMEKA_KEY_IDENTITY,
OMEKA_KEY_CREDENTIAL). All methods return parsed JSON.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Iterator
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def _load_env() -> dict[str, str]:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    out: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


class Omeka:
    def __init__(self) -> None:
        env = _load_env()
        self.base = (env.get("OMEKA_BASE_URL") or os.environ["OMEKA_BASE_URL"]).rstrip("/")
        self.auth = {
            "key_identity": env.get("OMEKA_KEY_IDENTITY") or os.environ["OMEKA_KEY_IDENTITY"],
            "key_credential": env.get("OMEKA_KEY_CREDENTIAL") or os.environ["OMEKA_KEY_CREDENTIAL"],
        }
        self.s = requests.Session()
        retry = Retry(total=5, backoff_factor=1.0,
                      status_forcelist=[500, 502, 503, 504],
                      allowed_methods=["GET", "POST", "PATCH"])
        adapter = HTTPAdapter(max_retries=retry, pool_connections=1, pool_maxsize=1)
        self.s.mount("http://", adapter); self.s.mount("https://", adapter)
        self.s.headers["Connection"] = "close"  # don't reuse — server kills idle
        self.s.headers["User-Agent"] = "jecke-cli/1.0"  # python-requests UA is blocked by WAF

    def get(self, path: str, **params: Any) -> Any:
        r = self.s.get(f"{self.base}/{path.lstrip('/')}", params={**self.auth, **params})
        r.raise_for_status()
        return r.json()

    def total(self, path: str, **params: Any) -> int:
        r = self.s.get(f"{self.base}/{path.lstrip('/')}", params={**self.auth, **params, "per_page": 1})
        r.raise_for_status()
        return int(r.headers.get("Omeka-S-Total-Results", "0"))

    def iter_items(self, *, per_page: int = 100, **params: Any) -> Iterator[dict]:
        page = 1
        while True:
            data = self.get("items", per_page=per_page, page=page, **params)
            if not data:
                return
            yield from data
            if len(data) < per_page:
                return
            page += 1

    def post(self, path: str, json: dict) -> dict:
        r = self.s.post(f"{self.base}/{path.lstrip('/')}", params=self.auth, json=json)
        r.raise_for_status()
        return r.json()

    def patch(self, path: str, json: dict) -> dict:
        r = self.s.patch(f"{self.base}/{path.lstrip('/')}", params=self.auth, json=json)
        r.raise_for_status()
        return r.json()
