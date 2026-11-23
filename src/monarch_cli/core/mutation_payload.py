"""Validate selected creation payloads before acknowledging a mutation."""

from typing import Any

from .exceptions import APIError


def created_record(data: Any, payload_field: str, record_field: str, *, fix: str) -> dict[str, Any]:
    """Require the canonical SDK root, no payload errors, and a nonempty record ID."""
    payload = data.get(payload_field) if isinstance(data, dict) and not data.get("errors") else None
    record = (
        payload.get(record_field)
        if isinstance(payload, dict) and not payload.get("errors")
        else None
    )
    if not isinstance(record, dict) or not isinstance(record.get("id"), str) or not record["id"]:
        raise APIError(
            "Could not confirm creation. Inspect before retrying.",
            details={"response": data, "fix": fix},
        )
    return record
