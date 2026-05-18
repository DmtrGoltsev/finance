"""Sanitization guards for fixture loader outputs.

The checks here are intentionally conservative for log and evidence metadata:
they reject key names that would imply raw secrets, raw bodies, financial values,
or account/category display names are being emitted.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


class SanitizationError(ValueError):
    """Raised when a fixture output contains forbidden evidence/log keys."""


_FORBIDDEN_KEY_PATTERNS = {
    "tokens": re.compile(r"(^|_)(plain)?tokens?($|_)|token(hash|hashes)?", re.IGNORECASE),
    "token_hashes": re.compile(r"token_?hash(es)?|tokenhash(es)?", re.IGNORECASE),
    "passwords": re.compile(r"(^|_)passwords?($|_)|plaintext_?passwords?", re.IGNORECASE),
    "raw_bodies": re.compile(
        r"raw_?(request|response)?_?bod(y|ies)|raw(financial)?payloads?",
        re.IGNORECASE,
    ),
    "amounts_in_logs": re.compile(r"(^|_)amounts?($|_)|balances?", re.IGNORECASE),
    "account_names_in_logs": re.compile(r"account_?names?", re.IGNORECASE),
    "category_names_in_logs": re.compile(r"category_?names?", re.IGNORECASE),
    "secrets": re.compile(r"(^|_)secrets?($|_)|production_?config", re.IGNORECASE),
}


def assert_safe_evidence_keys(value: Any, *, context: str = "evidence") -> None:
    """Reject forbidden keys in nested log/evidence structures.

    The function scans mapping keys only. Fixture labels and opaque synthetic ids
    are allowed as values, but output keys such as ``tokens``, ``rawBodies`` or
    ``amounts`` are never safe for release evidence or logs.
    """

    _scan(value, path=context)


def _scan(value: Any, *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            for reason, pattern in _FORBIDDEN_KEY_PATTERNS.items():
                if pattern.search(key_text):
                    raise SanitizationError(
                        f"Forbidden {reason} key at {path}.{key_text}"
                    )
            _scan(child, path=f"{path}.{key_text}")
        return

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            _scan(child, path=f"{path}[{index}]")
