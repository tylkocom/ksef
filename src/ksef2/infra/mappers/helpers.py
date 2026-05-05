"""Shared helpers used across request and response mappers."""

from collections.abc import Sequence
from datetime import datetime, date, UTC
from enum import StrEnum
from zoneinfo import ZoneInfo

from typing import TypeVar

K = TypeVar("K")
V = TypeVar("V")


def to_aware_datetime(dt: str | datetime | date) -> datetime:
    """Normalize naive Warsaw datetimes or ISO strings into UTC-aware datetimes."""
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("Europe/Warsaw"))
        return dt.astimezone(UTC)
    elif isinstance(dt, date):
        return datetime.combine(dt, datetime.min.time()).astimezone(UTC)
    else:
        return to_aware_datetime(datetime.fromisoformat(dt))


def lookup(mapping: dict[K, V], key: K, label: str) -> V:
    """Return a mapping value or raise a labeled ``ValueError``."""
    try:
        return mapping[key]
    except KeyError:
        expected = ", ".join(str(k) for k in mapping)
        raise ValueError(f"Unknown {label}: {key}. Expected one of: {expected}")


def get_matching_enum(
    value: str, enums: Sequence[type[StrEnum]]
) -> type[StrEnum] | None:
    """Find the single enum class whose members contain ``value``."""
    matches: list[type[StrEnum]] = []
    for enum_cls in enums:
        if any(member.value == value for member in enum_cls):
            matches.append(enum_cls)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(e.__name__ for e in matches)
        raise ValueError(
            f"Ambiguous enum mapping for {value!r}. Matches: {names}. "
            "Pass the explicit StrEnum value instead of a string."
        )
    return None
