from __future__ import annotations

from typing import Any

import streamlit as st
from supabase import Client, create_client

TABLE_NAME = "responses"


def _secret(name: str, default: Any = None) -> Any:
    try:
        return st.secrets.get(name, default)
    except (FileNotFoundError, KeyError):
        return default


@st.cache_resource
def get_client() -> Client:
    url = _secret("SUPABASE_URL")
    key = _secret("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise RuntimeError(
            "Faltan SUPABASE_URL ou SUPABASE_SECRET_KEY en .streamlit/secrets.toml."
        )
    return create_client(url, key)


def upsert_participant(
    payload: dict[str, Any],
) -> tuple[bool, str | None]:
    try:
        (
            get_client()
            .table(TABLE_NAME)
            .upsert(payload, on_conflict="participant_id")
            .execute()
        )
        return True, None
        except Exception as exc:
        print(
            f"SUPABASE DASHBOARD ERROR: {type(exc).__name__}: {exc}",
            flush=True,
        )
        return None, str(exc)


def fetch_participant(participant_id: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = (
            get_client()
            .table(TABLE_NAME)
            .select("*")
            .eq("participant_id", participant_id)
            .limit(1)
            .execute()
        )
        data = response.data or []
        return (data[0] if data else None), None
    except Exception as exc:
        return None, str(exc)


def condition_counts(include_demo: bool = False) -> tuple[dict[str, int] | None, str | None]:
    try:
        query = get_client().table(TABLE_NAME).select("condition")
        if not include_demo:
            query = query.eq("is_demo", False)
        response = query.execute()
        counts = {"small": 0, "large": 0, "algorithm": 0}
        for row in response.data or []:
            condition = row.get("condition")
            if condition in counts:
                counts[condition] += 1
        return counts, None
    except Exception as exc:
        return None, str(exc)


def fetch_completed(include_demo: bool = False) -> tuple[list[dict[str, Any]] | None, str | None]:
    try:
        query = get_client().table(TABLE_NAME).select("*").eq("status", "completed")
        if not include_demo:
            query = query.eq("is_demo", False)
        response = query.order("timestamp_utc", desc=False).execute()
        return response.data or [], None
    except Exception as exc:
        return None, str(exc)
