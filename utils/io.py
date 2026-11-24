"""File helpers for the outputs/<business_slug>/ handoff directory."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class HandoffError(RuntimeError):
    """A required upstream file is missing or invalid."""


def slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "business"


def write_json(path: Path, data: BaseModel | dict | list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = data.model_dump(mode="json") if isinstance(data, BaseModel) else data
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return path


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return path


def read_model(path: Path, schema: type[T]) -> T:
    if not path.exists():
        raise HandoffError(f"Missing required file: {path}. Run the earlier step first.")
    try:
        return schema.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise HandoffError(f"{path.name} does not match the {schema.__name__} schema:\n{exc}") from exc


def cell(value) -> str:
    """Escape a value for a markdown table cell."""
    return str(value).replace("|", "\\|").replace("\n", " ").strip()
