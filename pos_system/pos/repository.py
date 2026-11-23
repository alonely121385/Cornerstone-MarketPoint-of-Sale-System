"""JSON persistence for the point-of-sale application."""

from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INVENTORY = [
    {
        "barcode": "6900000000011",
        "name": "Spring Water 500 ml",
        "unit_price": "2.00",
        "quantity": 60,
    },
    {
        "barcode": "6900000000028",
        "name": "Whole Milk 1 L",
        "unit_price": "12.80",
        "quantity": 24,
    },
    {
        "barcode": "6900000000035",
        "name": "Wheat Bread",
        "unit_price": "8.50",
        "quantity": 18,
    },
    {
        "barcode": "6900000000042",
        "name": "Green Tea 500 ml",
        "unit_price": "5.00",
        "quantity": 36,
    },
    {
        "barcode": "6900000000059",
        "name": "Orange Juice 1 L",
        "unit_price": "15.90",
        "quantity": 16,
    },
    {
        "barcode": "6900000000066",
        "name": "Paper Towels",
        "unit_price": "18.00",
        "quantity": 12,
    },
]


class RepositoryError(Exception):
    """Raised when the application data cannot be read or written."""


def default_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "products": deepcopy(DEFAULT_INVENTORY),
        "transactions": [],
    }


class JsonRepository:
    """Store all POS state in one atomically written JSON file."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            state = default_state()
            self.save(state)
            return state

        try:
            with self.path.open("r", encoding="utf-8") as handle:
                state = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise RepositoryError(
                f"Could not read application data from {self.path}."
            ) from exc

        if not isinstance(state, dict):
            raise RepositoryError("Application data must be a JSON object.")
        if not isinstance(state.get("products"), list):
            raise RepositoryError("Application data has no valid product list.")
        if not isinstance(state.get("transactions"), list):
            raise RepositoryError("Application data has no valid transaction list.")
        return state

    def save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = handle.name
                json.dump(state, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
        except OSError as exc:
            if temporary_path:
                try:
                    Path(temporary_path).unlink(missing_ok=True)
                except OSError:
                    pass
            raise RepositoryError(
                f"Could not save application data to {self.path}."
            ) from exc
