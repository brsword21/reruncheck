"""Shared bounded inputs and expected operational errors."""

import math
from dataclasses import dataclass


class ReruncheckError(ValueError):
    """An incomplete observation or invalid request; never a clean result."""


@dataclass(frozen=True)
class Limits:
    max_entries: int = 10_000
    max_bytes: int = 64 * 1024 * 1024
    max_json_bytes: int = 16 * 1024 * 1024
    max_output_bytes: int = 1024 * 1024
    timeout: float = 10.0

    def __post_init__(self):
        ceilings = {
            "max_entries": 100_000,
            "max_bytes": 1024**3,
            "max_json_bytes": 64 * 1024**2,
            "max_output_bytes": 16 * 1024**2,
        }
        for key, ceiling in ceilings.items():
            value = getattr(self, key)
            minimum = 4096 if key == "max_json_bytes" else 1
            if type(value) is not int or not minimum <= value <= ceiling:
                raise ReruncheckError(f"{key} must be an integer in {minimum}..{ceiling}")
        if (
            type(self.timeout) not in (float, int)
            or not math.isfinite(self.timeout)
            or not 0 < self.timeout <= 3600
        ):
            raise ReruncheckError("timeout must be finite and in (0, 3600] seconds")
