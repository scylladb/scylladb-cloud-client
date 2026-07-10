"""Runtime client for the public ScyllaDB Cloud API."""

from __future__ import annotations

import json
import os
import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

from scylladb_cloud_client.operations import COMPONENTS, DEFINITIONS, OPERATION_REGISTRY

DEFAULT_BASE_URL = "https://api.cloud.scylladb.com"
PACKAGE_NAME = "scylladb-cloud-client"
_PATH_PARAM_RE = re.compile(r"\{([^{}]+)\}")


class ScyllaDBCloudAPIError(Exception):
    """Raised for expected client and API failures."""


def _package_version() -> str:
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        version_file = Path(__file__).resolve().parents[2] / "VERSION"
        try:
            return version_file.read_text(encoding="utf-8").strip()
        except OSError:
            return "unknown"


DEFAULT_USER_AGENT = f"{PACKAGE_NAME}/{_package_version()}"


def _missing_token_message() -> str:
    return "Missing ScyllaDB Cloud API token. Use --token or SCYLLA_CLOUD_API_KEY/SCYLLA_CLOUD_API_TOKEN."


def _normalize_base_url(base_url: str | None) -> str:
    """Return a non-empty HTTPS base URL without a trailing slash."""
    candidate = (base_url or DEFAULT_BASE_URL).strip()
    if not candidate:
        candidate = DEFAULT_BASE_URL
    parsed = urlparse(candidate)
    if parsed.scheme.lower() != "https":
        raise ScyllaDBCloudAPIError(
            "base_url must use the https scheme (plain http is not allowed). "
            f"Got scheme {parsed.scheme!r} in {candidate!r}."
        )
    if not parsed.netloc:
        raise ScyllaDBCloudAPIError(f"base_url must include a host after https:// (invalid URL: {candidate!r}).")
    return candidate.rstrip("/")


def operation_key(method: str, path: str) -> str:
    return f"{method.upper()} {path}"


def resolve_token(explicit_token: str | None = None) -> str | None:
    if explicit_token:
        return explicit_token.strip()
    for env_name in ("SCYLLA_CLOUD_API_KEY", "SCYLLA_CLOUD_API_TOKEN"):
        value = os.environ.get(env_name)
        if value and value.strip():
            return value.strip()
    return None


def _schema_ref_name(schema: Mapping[str, Any] | None) -> tuple[str, str] | None:
    ref = (schema or {}).get("$ref")
    if not ref:
        return None
    if ref.startswith("#/components/schemas/"):
        return ("components", ref.rsplit("/", 1)[-1])
    if ref.startswith("#/definitions/"):
        return ("definitions", ref.rsplit("/", 1)[-1])
    return None


def _resolve_schema(schema: Mapping[str, Any] | None, depth: int = 0) -> Mapping[str, Any]:
    if not schema or depth > 20:
        return schema or {}
    ref_name = _schema_ref_name(schema)
    if ref_name:
        source, name = ref_name
        source_map = COMPONENTS if source == "components" else DEFINITIONS
        return _resolve_schema(source_map.get(name, {}), depth + 1)
    if schema.get("allOf"):
        merged: dict[str, Any] = {}
        for entry in schema["allOf"]:
            resolved = _resolve_schema(entry, depth + 1)
            merged.update({k: v for k, v in resolved.items() if k != "properties"})
            if resolved.get("properties"):
                merged.setdefault("properties", {}).update(resolved["properties"])
            if resolved.get("required"):
                merged.setdefault("required", [])
                merged["required"].extend(v for v in resolved["required"] if v not in merged["required"])
        return merged
    return schema


def _coerce_scalar(value: Any, schema: Mapping[str, Any], name: str) -> Any:
    if value is None:
        return None
    schema = _resolve_schema(schema)
    enum_values = schema.get("enum")
    schema_type = schema.get("type")
    if schema_type == "integer":
        try:
            value = int(value)
        except (TypeError, ValueError) as exc:
            raise ScyllaDBCloudAPIError(f"{name} must be an integer") from exc
    elif schema_type == "number":
        try:
            value = float(value)
        except (TypeError, ValueError) as exc:
            raise ScyllaDBCloudAPIError(f"{name} must be a number") from exc
    elif schema_type == "boolean":
        if isinstance(value, bool):
            pass
        elif isinstance(value, str) and value.lower() in {"true", "1", "yes"}:
            value = True
        elif isinstance(value, str) and value.lower() in {"false", "0", "no"}:
            value = False
        else:
            raise ScyllaDBCloudAPIError(f"{name} must be a boolean")
    elif schema_type == "string" and not isinstance(value, str):
        value = str(value)
    if enum_values and value not in enum_values:
        allowed = ", ".join(str(item) for item in enum_values)
        raise ScyllaDBCloudAPIError(f"{name} must be one of: {allowed}")
    return value


def _coerce_value(value: Any, schema: Mapping[str, Any], name: str) -> Any:
    schema = _resolve_schema(schema)
    if schema.get("type") == "array":
        if isinstance(value, str):
            value = [item for item in value.split(",") if item != ""]
        elif not isinstance(value, (list, tuple)):
            value = [value]
        item_schema = schema.get("items") or {}
        return [_coerce_value(item, item_schema, name) for item in value]
    return _coerce_scalar(value, schema, name)


def _parameter_schema(parameter: Mapping[str, Any]) -> Mapping[str, Any]:
    schema = dict(parameter.get("schema") or {})
    for key in ("type", "format", "enum", "items"):
        if key in parameter and key not in schema:
            schema[key] = parameter[key]
    return schema


def validate_operation_input(
    operation: Mapping[str, Any],
    path_params: Mapping[str, Any] | None = None,
    query: Mapping[str, Any] | None = None,
    body: Any = None,
) -> tuple[dict[str, Any], dict[str, Any], Any]:
    path_params = dict(path_params or {})
    query = dict(query or {})
    validated_path = _validate_parameters(operation.get("path_parameters") or [], path_params, "path")
    validated_query = _validate_parameters(operation.get("query_parameters") or [], query, "query")

    body_schema = operation.get("body_schema")
    if body_schema and body is None:
        raise ScyllaDBCloudAPIError("Request body is required")
    if body_schema:
        _validate_body(body, body_schema)
    return validated_path, validated_query, body


def _validate_parameters(parameters: list[Mapping[str, Any]], values: dict[str, Any], label: str) -> dict[str, Any]:
    validated: dict[str, Any] = {}
    for parameter in parameters:
        name = parameter["name"]
        if name not in values or values[name] in (None, ""):
            if parameter.get("required"):
                raise ScyllaDBCloudAPIError(f"Missing required {label} parameter: {name}")
            continue
        validated[name] = _coerce_value(values[name], _parameter_schema(parameter), name)
    unknown = sorted(set(values) - {parameter["name"] for parameter in parameters})
    if unknown:
        raise ScyllaDBCloudAPIError(f"Unknown {label} parameter(s): {', '.join(unknown)}")
    return validated


def _validate_body(value: Any, schema: Mapping[str, Any], path: str = "body") -> None:
    schema = _resolve_schema(schema)
    schema_type = schema.get("type")
    if schema_type == "object" or schema.get("properties"):
        if not isinstance(value, Mapping):
            raise ScyllaDBCloudAPIError(f"{path} must be a JSON object")
        properties = schema.get("properties") or {}
        if schema.get("additionalProperties", False) is False:
            unknown = sorted(set(value) - set(properties))
            if unknown:
                raise ScyllaDBCloudAPIError(f"Unknown {path} field(s): {', '.join(unknown)}")
        for field in schema.get("required") or []:
            if field not in value:
                raise ScyllaDBCloudAPIError(f"{path}.{field} is required")
        for field, field_schema in properties.items():
            if field in value and value[field] is not None:
                _validate_body(value[field], field_schema, f"{path}.{field}")
    elif schema_type == "array":
        if not isinstance(value, list):
            raise ScyllaDBCloudAPIError(f"{path} must be a JSON array")
        for index, item in enumerate(value):
            _validate_body(item, schema.get("items") or {}, f"{path}[{index}]")
    elif schema_type in {"integer", "number", "boolean", "string"}:
        _coerce_scalar(value, schema, path)


def _query_value_for_url(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ",".join(str(_query_value_for_url(item)) for item in value)
    if isinstance(value, tuple):
        return ",".join(str(_query_value_for_url(item)) for item in value)
    return value


class ScyllaDBCloudClient:
    def __init__(
        self,
        token: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 30,
        debug: bool = False,
    ):
        self.token = resolve_token(token)
        self.base_url = _normalize_base_url(base_url)
        self.timeout = timeout
        self.debug = debug

    def execute(
        self,
        method: str,
        path: str,
        *,
        path_params: Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
        body: Any = None,
    ) -> dict[str, Any]:
        key = operation_key(method, path)
        operation = OPERATION_REGISTRY.get(key)
        if operation is None:
            raise ScyllaDBCloudAPIError(f"Unsupported public ScyllaDB Cloud API operation: {key}")
        requires_auth = operation.get("requires_auth", True)
        if requires_auth and not self.token:
            raise ScyllaDBCloudAPIError(_missing_token_message())
        path_params, query, body = validate_operation_input(operation, path_params, query, body)
        return self.request(
            operation["method"],
            operation["path"],
            path_params=path_params,
            query=query,
            body=body,
            requires_auth=requires_auth,
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        path_params: Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
        body: Any = None,
        requires_auth: bool = True,
    ) -> dict[str, Any]:
        url = self._url_for(path, path_params, query)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }
        if requires_auth:
            if not self.token:
                raise ScyllaDBCloudAPIError(_missing_token_message())
            headers["Authorization"] = f"Bearer {self.token}"
        if self.debug:
            print(f"ScyllaDB Cloud API request: {method.upper()} {url}")
        request = Request(url, data=data, headers=headers, method=method.upper())
        try:
            with urlopen(request, timeout=self.timeout) as response:
                response_body = response.read().decode("utf-8")
                return self._response_payload(response.status, dict(response.headers), response_body)
        except HTTPError as exc:
            response_body = exc.read().decode("utf-8", "replace")
            parsed = self._parse_response(response_body)
            detail = parsed if isinstance(parsed, str) else json.dumps(parsed, ensure_ascii=False, default=str)
            raise ScyllaDBCloudAPIError(f"ScyllaDB Cloud API returned HTTP {exc.code}: {detail[:500]}") from exc
        except URLError as exc:
            raise ScyllaDBCloudAPIError(f"ScyllaDB Cloud API request failed: {exc}") from exc

    def _url_for(
        self,
        path: str,
        path_params: Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
    ) -> str:
        path_params = path_params or {}

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in path_params:
                raise ScyllaDBCloudAPIError(f"Missing path parameter: {name}")
            return quote(str(path_params[name]), safe="")

        rendered_path = _PATH_PARAM_RE.sub(replace, path)
        query_for_url = {key: _query_value_for_url(value) for key, value in (query or {}).items() if value is not None}
        url = f"{self.base_url}{rendered_path}"
        if query_for_url:
            url = f"{url}?{urlencode(query_for_url, safe=',')}"
        return url

    @staticmethod
    def _parse_response(response_body: str) -> Any:
        if not response_body:
            return None
        try:
            return json.loads(response_body)
        except ValueError:
            return response_body

    def _response_payload(self, status_code: int, headers: Mapping[str, str], response_body: str) -> dict[str, Any]:
        parsed = self._parse_response(response_body)
        if self.debug:
            print(f"ScyllaDB Cloud API response: status={status_code}")
        if isinstance(parsed, Mapping) and parsed.get("error"):
            detail = json.dumps(parsed, ensure_ascii=False, default=str)
            raise ScyllaDBCloudAPIError(f"ScyllaDB Cloud API returned error {parsed['error']}: {detail[:500]}")
        return {
            "status": "success",
            "status_code": status_code,
            "data": parsed,
            "headers": dict(headers),
        }
