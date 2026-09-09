"""Horodatages UTC, convention du schema (TEXT ISO 8601)."""

from datetime import UTC, date, datetime


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_today() -> date:
    return datetime.now(UTC).date()
