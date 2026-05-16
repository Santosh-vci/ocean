from __future__ import annotations

import logging
import re
from collections.abc import Iterable

SENSITIVE_KEYWORDS = (
    "authorization",
    "cookie",
    "csrf",
    "password",
    "secret",
    "token",
)

SENSITIVE_PATTERN = re.compile(
    r"(?i)\b(cookie|csrf|password|secret|token)"
    r"(\s*[=:]\s*|\s+)([^,\s\]}]+)"
)
AUTH_PATTERN = re.compile(r"(?i)\b(authorization)(\s*[=:]\s*|\s+)(Bearer\s+)?([^,\s\]}]+)")


def redact_sensitive(value: object) -> str:
    text = str(value)
    text = AUTH_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", text)
    return SENSITIVE_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", text)


class SensitiveDataFilter(logging.Filter):
    """Redact common credential material before log records reach stdout."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact_sensitive(record.getMessage())
            record.args = ()
        except Exception:
            record.msg = "[log redaction failed]"
            record.args = ()
        return True


def redacted_mapping(data: dict | None, *, extra_keys: Iterable[str] = ()) -> dict:
    if not data:
        return {}

    sensitive_keys = {keyword.lower() for keyword in SENSITIVE_KEYWORDS}
    sensitive_keys.update(key.lower() for key in extra_keys)
    redacted = {}
    for key, value in data.items():
        if str(key).lower() in sensitive_keys:
            redacted[key] = "[REDACTED]"
        else:
            redacted[key] = value
    return redacted
