"""Thin client for the Omeka S REST API.

Credentials are read from ../.env (OMEKA_BASE_URL, OMEKA_KEY_IDENTITY,
OMEKA_KEY_CREDENTIAL). All methods return parsed JSON.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Iterator
import requests


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
