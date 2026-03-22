"""Lightweight JSON Schema validation for local contract enforcement."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


class ContractValidationError(ValueError):
    """Raised when a payload does not conform to a local contract schema."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=32)
def load_contract_schema(relative_path: str) -> dict[str, Any]:
    """Load and cache a contract schema from the repo-level contracts directory."""
    path = _repo_root() / relative_path
    return json.loads(path.read_text(encoding="utf-8"))


def validate_contract_payload(*, schema: dict[str, Any], payload: Any) -> None:
    """Validate one JSON payload against the supported schema subset."""
    _validate_node(schema=schema, value=payload, path="$")


def _validate_node(*, schema: dict[str, Any], value: Any, path: str) -> None:
    expected_type = schema.get("type")
    if expected_type is not None and not _matches_type(expected_type, value):
        raise ContractValidationError(
            f"{path}: expected {_describe_type(expected_type)}, got {_python_type_name(value)}"
        )

    if "enum" in schema and value not in schema["enum"]:
        raise ContractValidationError(f"{path}: value {value!r} is not in allowed enum")

    if value is None:
        return

    if isinstance(value, (int, float)) and "minimum" in schema:
        if value < schema["minimum"]:
            raise ContractValidationError(f"{path}: must be >= {schema['minimum']}")

    node_type = _primary_type(expected_type, value)
    if node_type == "object":
        _validate_object(schema=schema, value=value, path=path)
    elif node_type == "array":
        _validate_array(schema=schema, value=value, path=path)


def _validate_object(*, schema: dict[str, Any], value: Any, path: str) -> None:
    if not isinstance(value, dict):
        raise ContractValidationError(f"{path}: expected object, got {_python_type_name(value)}")

    required = schema.get("required", [])
    for key in required:
        if key not in value:
            raise ContractValidationError(f"{path}: missing required property {key!r}")

    properties = schema.get("properties", {})
    additional_properties = schema.get("additionalProperties", True)

    if additional_properties is False:
        unexpected = sorted(set(value.keys()) - set(properties.keys()))
        if unexpected:
            raise ContractValidationError(
                f"{path}: unexpected properties {', '.join(repr(item) for item in unexpected)}"
            )

    for key, child in properties.items():
        if key in value:
            _validate_node(schema=child, value=value[key], path=f"{path}.{key}")


def _validate_array(*, schema: dict[str, Any], value: Any, path: str) -> None:
    if not isinstance(value, list):
        raise ContractValidationError(f"{path}: expected array, got {_python_type_name(value)}")
    item_schema = schema.get("items")
    if not isinstance(item_schema, dict):
        return
    for index, item in enumerate(value):
        _validate_node(schema=item_schema, value=item, path=f"{path}[{index}]")


def _matches_type(expected_type: Any, value: Any) -> bool:
    if isinstance(expected_type, list):
        return any(_matches_type(item, value) for item in expected_type)
    if expected_type == "null":
        return value is None
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return (isinstance(value, int) and not isinstance(value, bool)) or isinstance(value, float)
    if expected_type == "boolean":
        return isinstance(value, bool)
    return True


def _primary_type(expected_type: Any, value: Any) -> str | None:
    if isinstance(expected_type, list):
        for item in expected_type:
            if _matches_type(item, value):
                return item
        return None
    if isinstance(expected_type, str) and _matches_type(expected_type, value):
        return expected_type
    return None


def _describe_type(expected_type: Any) -> str:
    if isinstance(expected_type, list):
        return " | ".join(str(item) for item in expected_type)
    return str(expected_type)


def _python_type_name(value: Any) -> str:
    return type(value).__name__
