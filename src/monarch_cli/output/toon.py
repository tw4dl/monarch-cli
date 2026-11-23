"""TOON 4.4 encoder for JSON-shaped data, with no runtime dependencies.

Normalization: date/time uses ISO 8601; tuples become arrays; other host values
use str, as the existing JSON boundary does. Integers retain Python precision.
Non-finite floats become null. Cycles and surrogate code points are rejected.
The returned document has no trailing newline. CLI transport may append one.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
_NUMERIC = re.compile(r"^[+-]?[0-9]+(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?$", re.IGNORECASE)
_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}


def _string(value: str) -> str:
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ValueError("TOON cannot encode surrogate code points")
    return value


def _normalize(value: Any, seen: set[int]) -> Any:
    if isinstance(value, str):
        return _string(value)
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (dict, list, tuple)):
        identity = id(value)
        if identity in seen:
            raise ValueError("TOON cannot encode circular data")
        seen.add(identity)
        try:
            if isinstance(value, dict):
                result: dict[str, Any] = {}
                for key, item in value.items():
                    normalized_key = _string(str(key))
                    if normalized_key in result:
                        raise ValueError("TOON normalization produced duplicate object keys")
                    result[normalized_key] = _normalize(item, seen)
                return result
            return [_normalize(item, seen) for item in value]
        finally:
            seen.remove(identity)
    return _string(str(value))


def _quote(value: str) -> str:
    return (
        '"'
        + "".join(
            _ESCAPES.get(char, f"\\u{ord(char):04x}" if ord(char) < 0x20 else char)
            for char in value
        )
        + '"'
    )


def _key(value: str) -> str:
    return value if _KEY.fullmatch(value) else _quote(value)


def _primitive(value: Any) -> bool:
    return not isinstance(value, (dict, list))


def _shape(rows: list[Any]) -> dict[str, Any] | None:
    """Find uniform primitive columns and recursively uniform object columns."""
    if not rows or any(not isinstance(row, dict) or not row for row in rows):
        return None
    first: dict[str, Any] = rows[0]
    if any(set(row) != set(first) for row in rows):
        return None
    shape: dict[str, Any] = {}
    for key in first:
        values = [row[key] for row in rows]
        if all(_primitive(value) for value in values):
            shape[key] = None
        else:
            nested = _shape(values)
            if nested is None:
                return None
            shape[key] = nested
    return shape


class _Encoder:
    def __init__(self, delimiter: str, indent: int) -> None:
        self.delimiter = delimiter
        self.marker = "" if delimiter == "," else delimiter
        self.indent = indent

    def scalar(self, value: Any, *, root: bool = False) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            if value == 0:
                return "0"
            if 1e-6 <= abs(value) < 1e21:
                number = format(Decimal(repr(value)), "f")
                return number.rstrip("0").rstrip(".") if "." in number else number
            return repr(value)
        must_quote = (
            not value
            or value[0] in " \t-#"
            or value[-1] in " \t"
            or value in {"true", "false", "null"}
            or _NUMERIC.fullmatch(value)
            or any(char in ':"\\[]{}' + self.delimiter or ord(char) < 0x20 for char in value)
            or (root and value.startswith("\ufeff"))
        )
        return _quote(value) if must_quote else str(value)

    def fields(self, shape: dict[str, Any]) -> str:
        return self.delimiter.join(
            _key(key) + ("{" + self.fields(nested) + "}" if nested is not None else "")
            for key, nested in shape.items()
        )

    def cells(self, row: dict[str, Any], shape: dict[str, Any]) -> list[str]:
        result: list[str] = []
        for key, nested in shape.items():
            result.extend(
                self.cells(row[key], nested) if nested is not None else [self.scalar(row[key])]
            )
        return result

    def line(self, depth: int, text: str) -> str:
        return " " * (depth * self.indent) + text

    def value(self, value: Any, key: str | None, depth: int, *, table: bool = True) -> list[str]:
        label = _key(key) if key is not None else ""
        if _primitive(value):
            text = (label + ": " if key is not None else "") + self.scalar(value, root=key is None)
            return [self.line(depth, text)]
        if isinstance(value, dict):
            shape = _shape(list(value.values())) if len(value) >= 2 and table else None
            if shape is not None:
                header = f"{label}[{len(value)}:{self.marker}]{{{self.fields(shape)}}}:"
                return [self.line(depth, header)] + [
                    self.line(
                        depth + 1, _key(entry) + ": " + self.delimiter.join(self.cells(row, shape))
                    )
                    for entry, row in value.items()
                ]
            lines = [self.line(depth, label + ":")] if key is not None else []
            for child_key, child in value.items():
                lines.extend(self.value(child, child_key, depth + (key is not None)))
            return lines
        if not value:
            return [self.line(depth, label + ": []" if key is not None else "[]")]
        header = f"{label}[{len(value)}{self.marker}]"
        if all(_primitive(item) for item in value):
            return [self.line(depth, header + ": " + self.delimiter.join(map(self.scalar, value)))]
        shape = _shape(value) if table else None
        if shape is not None:
            return [self.line(depth, header + "{" + self.fields(shape) + "}:")] + [
                self.line(depth + 1, self.delimiter.join(self.cells(row, shape))) for row in value
            ]
        lines = [self.line(depth, header + ":")]
        for item in value:
            lines.extend(self.item(item, depth + 1))
        return lines

    def item(self, value: Any, depth: int) -> list[str]:
        if isinstance(value, dict):
            if not value:
                return [self.line(depth, "-")]
            lines: list[str] = []
            for index, (key, child) in enumerate(value.items()):
                fields = self.value(child, key, depth + 1)
                if index == 0:
                    fields[0] = self.line(depth, "- " + fields[0].lstrip(" "))
                lines.extend(fields)
            return lines
        if isinstance(value, list) and not value:
            return [self.line(depth, f"- [0{self.marker}]:")]
        lines = self.value(value, None, depth, table=False)
        lines[0] = self.line(depth, "- " + lines[0].lstrip(" "))
        return lines


def encode(value: Any, *, delimiter: str = ",", indent: int = 2) -> str:
    """Encode using TOON 4.4 canonical shapes, delimiters, and indentation."""
    if delimiter not in (",", "\t", "|"):
        raise ValueError("TOON delimiter must be comma, tab, or pipe")
    if type(indent) is not int or indent < 1:
        raise ValueError("TOON indent must be a positive integer")
    return "\n".join(_Encoder(delimiter, indent).value(_normalize(value, set()), None, 0))
