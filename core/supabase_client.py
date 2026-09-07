"""Small dependency-free Supabase REST client for the desktop registration workflow."""
from __future__ import annotations

import json
import os
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

DEFAULT_URL = "https://sxfnrwugsyfypqgfglzc.supabase.co"
DEFAULT_TABLE = "Class_X_reg_2026_2027"
DEFAULT_PUBLISHABLE_KEY = "sb_publishable_NARdPew6T6Zk8gYfxY3Hog_G7jcceKw"


class SupabaseError(RuntimeError):
    pass


class SupabaseClient:
    def __init__(self, url: str | None = None, key: str | None = None, timeout: int = 20):
        self.url = (url or os.getenv("SUPABASE_URL") or DEFAULT_URL).rstrip("/")
        self.key = key or os.getenv("SUPABASE_PUBLISHABLE_KEY") or DEFAULT_PUBLISHABLE_KEY
        self.timeout = timeout

    def select(self, table: str, filters: dict[str, str] | None = None, limit: int = 25) -> list[dict]:
        params = {"select": "*", "limit": str(limit)}
        for column, value in (filters or {}).items():
            params[column] = f"eq.{value}"
        url = f"{self.url}/rest/v1/{quote(table, safe='') }?{urlencode(params)}"
        request = Request(url, headers={"apikey": self.key, "Accept": "application/json"}, method="GET")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise SupabaseError(f"Supabase request failed: {exc}") from exc
        if not isinstance(payload, list):
            raise SupabaseError(f"Unexpected Supabase response: {payload}")
        return payload

    def search_students(self, query: str, limit: int = 25) -> list[dict]:
        query = (query or "").strip()
        if not query:
            return self.select(DEFAULT_TABLE, limit=limit)
        # PostgREST OR expression across the most useful matching fields.
        params = {
            "select": "*",
            "limit": str(limit),
            "or": f"Name.ilike.*{query}*,Father Name.ilike.*{query}*,Mother Name.ilike.*{query}*,Application No.eq.{query}",
        }
        url = f"{self.url}/rest/v1/{quote(DEFAULT_TABLE, safe='')}?{urlencode(params)}"
        request = Request(url, headers={"apikey": self.key, "Accept": "application/json"}, method="GET")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise SupabaseError(f"Supabase search failed: {exc}") from exc
        if not isinstance(payload, list):
            raise SupabaseError(f"Unexpected Supabase response: {payload}")
        return payload
