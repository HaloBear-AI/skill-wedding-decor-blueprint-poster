"""Validate a wedding decor blueprint poster specification."""

import argparse
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Collection, Union


_MISSING = object()
_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_PROHIBITED_TEXT = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029\ud800-\udfff]")
_LANGUAGE = re.compile(r"(?:[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*|[xXiI](?:-[A-Za-z0-9]{1,8})+)")
_ACCENT = re.compile(r"#[A-Fa-f0-9]{6}")
_DIMENSION = re.compile(
    r"(?=[0-9.]*[1-9])(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)"
    r"[ \u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]*"
    r"(?:mm|cm|m|in|ft|毫米|厘米|公分|米|英寸|英尺)"
)
_ROOT_FIELDS = (
    "schema_version",
    "language",
    "theme",
    "subtitle_elements",
    "labels",
    "views",
    "dimensions",
    "materials",
    "components",
    "steps",
)
_LABEL_LIMITS = {
    "title_suffix": 42,
    "materials": 28,
    "material_name": 20,
    "material_detail": 26,
    "components": 32,
    "steps": 32,
    "pending_measurement": 16,
    "missing_asset": 22,
    "disclaimer": 100,
}
_DIMENSION_KEYS = ("H", "W", "D", "A")


class _ObjectPairs(list):
    """Preserve object keys until their JSON paths are known."""


class _NonJSONConstant(str):
    """Mark a numeric token outside the JSON grammar."""


def _property_path(path: str, key: str) -> str:
    if _KEY.fullmatch(key):
        return f"{path}.{key}"
    return f"{path}[{json.dumps(key, ensure_ascii=True)}]"


def _materialize_json(value: Any, path: str, errors: list[str]) -> Any:
    if isinstance(value, _ObjectPairs):
        result = {}
        for key, child in value:
            child_path = _property_path(path, key)
            if key in result:
                errors.append(f"{child_path}: duplicate key")
            result[key] = _materialize_json(child, child_path, errors)
        return result
    if isinstance(value, list):
        return [
            _materialize_json(child, f"{path}[{index}]", errors)
            for index, child in enumerate(value)
        ]
    if isinstance(value, _NonJSONConstant):
        errors.append(f"{path}: {value} is not a valid JSON number")
    return value


class _SpecValidator:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def _error(self, path: str, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def _object(
        self,
        value: Any,
        path: str,
        required: Collection[str],
        optional: Collection[str] = (),
    ) -> dict[str, Any]:
        if value is _MISSING:
            return {}
        if not isinstance(value, dict):
            self._error(path, "must be an object")
            return {}
        for key in required:
            if key not in value:
                self._error(_property_path(path, key), "is required")
        for key in value:
            if key not in required and key not in optional:
                self._error(_property_path(path, key), "is an unknown key")
        return value

    def _array(
        self, value: Any, path: str, minimum: int, maximum: int
    ) -> list[Any]:
        if value is _MISSING:
            return []
        if not isinstance(value, list):
            self._error(path, "must be an array")
            return []
        if not minimum <= len(value) <= maximum:
            count = f"exactly {minimum}" if minimum == maximum else f"{minimum} to {maximum}"
            self._error(path, f"must contain {count} items (found {len(value)})")
        return value

    def _text(
        self, value: Any, path: str, limit: int, allow_null: bool = False
    ) -> bool:
        if value is _MISSING or (allow_null and value is None):
            return False
        if not isinstance(value, str):
            expected = "a string or null" if allow_null else "a string"
            self._error(path, f"must be {expected}")
            return False
        prior_errors = len(self.errors)
        if not value:
            self._error(path, "must have at least one character")
        elif value != value.strip():
            self._error(path, "must have no leading or trailing whitespace")
        if len(value) > limit:
            self._error(path, f"must have at most {limit} characters (found {len(value)})")
        if _PROHIBITED_TEXT.search(value):
            self._error(path, "must be single-line text without control or surrogate characters")
        return len(self.errors) == prior_errors

    def _integer(self, value: Any, path: str, expected: int) -> None:
        if value is not _MISSING and (type(value) is not int or value != expected):
            self._error(path, f"must be the integer {expected}")

    def _aisle_span(self, value: Any, path: str) -> None:
        if value is None:
            return
        endpoints = self._array(value, path, 2, 2)
        prior_errors = len(self.errors)
        for index, endpoint in enumerate(endpoints):
            if type(endpoint) not in (int, Decimal) or not 0 <= endpoint <= 1:
                self._error(f"{path}[{index}]", "must be a number from 0 to 1")
        if len(endpoints) == 2 and len(self.errors) == prior_errors:
            if endpoints[0] >= endpoints[1]:
                self._error(path, "must place the left endpoint strictly before the right endpoint")

    def _view(self, value: Any, path: str, allow_aisle: bool = False) -> None:
        optional = ("aisle_span",) if allow_aisle else ()
        view = self._object(value, path, ("heading", "prompt_detail"), optional)
        self._text(view.get("heading", _MISSING), f"{path}.heading", 32)
        self._text(view.get("prompt_detail", _MISSING), f"{path}.prompt_detail", 480, allow_null=True)
        if allow_aisle:
            self._aisle_span(view.get("aisle_span", _MISSING), f"{path}.aisle_span")

    def validate(self, value: Any) -> None:
        spec = self._object(value, "$", _ROOT_FIELDS, ("brand_name", "palette"))
        self._integer(spec.get("schema_version", _MISSING), "$.schema_version", 1)
        language = spec.get("language", _MISSING)
        if self._text(language, "$.language", 35) and not _LANGUAGE.fullmatch(language):
            self._error("$.language", "must use a language tag such as zh-CN or en")
        self._text(spec.get("theme", _MISSING), "$.theme", 96)
        self._text(spec.get("brand_name", _MISSING), "$.brand_name", 48, allow_null=True)

        palette = self._object(spec.get("palette", _MISSING), "$.palette", ("accent",))
        accent = palette.get("accent", _MISSING)
        if self._text(accent, "$.palette.accent", 7) and not _ACCENT.fullmatch(accent):
            self._error("$.palette.accent", "must use the format #RRGGBB")

        elements = self._array(spec.get("subtitle_elements", _MISSING), "$.subtitle_elements", 3, 3)
        for index, element in enumerate(elements):
            self._text(element, f"$.subtitle_elements[{index}]", 24)

        labels = self._object(spec.get("labels", _MISSING), "$.labels", _LABEL_LIMITS.keys())
        for key, limit in _LABEL_LIMITS.items():
            self._text(labels.get(key, _MISSING), f"$.labels.{key}", limit)

        views = self._object(spec.get("views", _MISSING), "$.views", ("elevation", "plan"))
        self._view(views.get("elevation", _MISSING), "$.views.elevation")
        self._view(views.get("plan", _MISSING), "$.views.plan", allow_aisle=True)

        dimensions = self._object(spec.get("dimensions", _MISSING), "$.dimensions", _DIMENSION_KEYS)
        for key in _DIMENSION_KEYS:
            path = f"$.dimensions.{key}"
            dimension = self._object(dimensions.get(key, _MISSING), path, ("label", "value"))
            self._text(dimension.get("label", _MISSING), f"{path}.label", 20)
            measure = dimension.get("value", _MISSING)
            if self._text(measure, f"{path}.value", 24, allow_null=True):
                if not _DIMENSION.fullmatch(measure):
                    self._error(
                        f"{path}.value",
                        "must be a positive decimal with a supported unit such as 2.4 m or 90cm",
                    )

        materials = self._array(spec.get("materials", _MISSING), "$.materials", 5, 8)
        for index, value in enumerate(materials):
            path = f"$.materials[{index}]"
            material = self._object(value, path, ("name", "detail"))
            self._text(material.get("name", _MISSING), f"{path}.name", 24)
            self._text(material.get("detail", _MISSING), f"{path}.detail", 48)

        components = self._array(spec.get("components", _MISSING), "$.components", 6, 6)
        for index, value in enumerate(components):
            path = f"$.components[{index}]"
            component = self._object(value, path, ("name", "prompt_detail"))
            self._text(component.get("name", _MISSING), f"{path}.name", 24)
            self._text(
                component.get("prompt_detail", _MISSING), f"{path}.prompt_detail", 300, allow_null=True
            )

        steps = self._array(spec.get("steps", _MISSING), "$.steps", 5, 5)
        for index, value in enumerate(steps):
            path = f"$.steps[{index}]"
            step = self._object(value, path, ("number", "name", "description", "prompt_detail"))
            self._integer(step.get("number", _MISSING), f"{path}.number", index + 1)
            self._text(step.get("name", _MISSING), f"{path}.name", 24)
            self._text(step.get("description", _MISSING), f"{path}.description", 54)
            self._text(step.get("prompt_detail", _MISSING), f"{path}.prompt_detail", 480, allow_null=True)


def load_spec(path: Union[str, Path]) -> dict[str, Any]:
    """Read and validate a UTF-8 JSON file. Raise ValueError with its diagnostics."""
    spec_path = Path(path)
    try:
        content = spec_path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(f"{spec_path} must contain valid UTF-8") from error
    except OSError as error:
        raise ValueError(f"Could not read {spec_path} ({error.strerror})") from error

    parse_errors: list[str] = []
    try:
        parsed = json.loads(
            content,
            object_pairs_hook=_ObjectPairs,
            parse_constant=_NonJSONConstant,
            parse_float=Decimal,
        )
        spec = _materialize_json(parsed, "$", parse_errors)
    except json.JSONDecodeError as error:
        raise ValueError(f"{spec_path} contains invalid JSON ({error})") from error
    except RecursionError as error:
        raise ValueError(f"{spec_path} contains deeply nested JSON") from error
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{spec_path} contains a number outside the supported range") from error

    if parse_errors:
        raise ValueError("\n".join([f"{spec_path} contains invalid JSON", *parse_errors]))
    validator = _SpecValidator()
    validator.validate(spec)
    if validator.errors:
        raise ValueError("\n".join([f"Invalid decor specification in {spec_path}", *validator.errors]))

    # Check decimal bounds before converting to the numeric types used by the renderer.
    plan = spec["views"]["plan"]
    if plan.get("aisle_span") is not None:
        plan["aisle_span"] = [
            float(endpoint) if isinstance(endpoint, Decimal) else endpoint
            for endpoint in plan["aisle_span"]
        ]
    return spec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True, help="UTF-8 JSON specification")
    options = parser.parse_args()
    try:
        load_spec(options.spec)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"Validated {options.spec}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
