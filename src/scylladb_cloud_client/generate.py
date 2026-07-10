"""Generate operation metadata from Swagger with a public-docs whitelist."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from pprint import pformat
from typing import Any
from urllib.request import urlopen

DEFAULT_SWAGGER_PATH = "../siren/restapi/docs/swagger.json"
DEFAULT_PUBLIC_SPEC_URL = "https://cloud.docs.scylladb.com/stable/_static/swagger.json"
DEFAULT_OUTPUT_PATH = "src/scylladb_cloud_client/operations.py"
PUBLIC_DOCS_URL = "https://cloud.docs.scylladb.com/stable/api.html"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}

PUBLIC_TO_LOCAL_ALIASES = {
    ("GET", "/account/{accountId}/clusters"): "/account/{account}/cluster",
    ("GET", "/account/{accountId}/cluster/{clusterId}/dcs"): "/account/{account}/cluster/{cluster}/dc",
    ("GET", "/account/{accountId}/cluster/{clusterId}/nodes"): "/account/{account}/cluster/{cluster}/node",
    ("GET", "/deployment/cloud-providers"): "/deployment/provider",
    ("GET", "/deployment/cloud-provider/{cloudProviderId}/regions"): "/deployment/provider/{provider}/region",
    ("GET", "/deployment/cloud-provider/{cloudProviderId}/region/{regionId}"): "/deployment/provider/{provider}/region/{region}/instance",
    ("GET", "/deployment/scylla-versions"): "/deployment/service/{service}/version",
}


def _load_json(path_or_url: str) -> dict[str, Any]:
    if path_or_url.startswith(("http://", "https://")):
        with urlopen(path_or_url, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    return json.loads(Path(path_or_url).expanduser().read_text(encoding="utf-8"))


def _operation_name(method: str, path: str, operation: dict[str, Any]) -> str:
    if operation.get("operationId"):
        return re.sub(r"[^A-Za-z0-9_]+", "_", operation["operationId"]).strip("_")
    return re.sub(r"[^A-Za-z0-9]+", "_", f"{method}_{path}").strip("_").lower()


def _normalize_path(path: str) -> str:
    return re.sub(r"\{[^{}]+\}", "{}", path)


def _extract_schema(parameter: dict[str, Any]) -> dict[str, Any]:
    schema = dict(parameter.get("schema") or {})
    for key in ("type", "format", "enum", "items"):
        if key in parameter and key not in schema:
            schema[key] = parameter[key]
    return schema


def _extract_parameters(parameters: list[dict[str, Any]], location: str) -> list[dict[str, Any]]:
    out = []
    for parameter in parameters:
        if parameter.get("in") != location:
            continue
        out.append(
            {
                "name": parameter.get("name"),
                "required": bool(parameter.get("required", False)),
                "schema": _extract_schema(parameter),
                "description": parameter.get("description"),
            }
        )
    return out


def _extract_body_schema(operation: dict[str, Any], parameters: list[dict[str, Any]]) -> dict[str, Any] | None:
    for parameter in parameters:
        if parameter.get("in") == "body":
            return parameter.get("schema") or {}
    request_body = operation.get("requestBody") or {}
    content = request_body.get("content") or {}
    for content_type in ("application/json", "application/*+json"):
        if content_type in content:
            return content[content_type].get("schema") or {}
    if content:
        first_media_type = next(iter(content.values()))
        return first_media_type.get("schema") or {}
    return None


def build_operation_registry(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    operations = {}
    for path, path_item in sorted((spec.get("paths") or {}).items()):
        path_parameters = path_item.get("parameters") or []
        for method, operation in sorted(path_item.items()):
            if method not in HTTP_METHODS:
                continue
            parameters = list(path_parameters) + list(operation.get("parameters") or [])
            method_upper = method.upper()
            key = f"{method_upper} {path}"
            operations[key] = {
                "key": key,
                "name": _operation_name(method_upper, path, operation),
                "method": method_upper,
                "path": path,
                "tags": operation.get("tags") or [],
                "summary": operation.get("summary") or "",
                "description": operation.get("description") or "",
                "path_parameters": _extract_parameters(parameters, "path"),
                "query_parameters": _extract_parameters(parameters, "query"),
                "body_schema": _extract_body_schema(operation, parameters),
                "responses": operation.get("responses") or {},
                "requires_auth": bool(operation.get("security")) or "BearerKeyAuth" in str(operation),
            }
    return operations


def _index_by_normalized_path(operations: dict[str, dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (operation["method"], _normalize_path(operation["path"])): operation
        for operation in operations.values()
    }


def generate_operations(source_swagger: dict[str, Any], public_spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    source_operations = build_operation_registry(source_swagger)
    public_operations = build_operation_registry(public_spec)
    source_index = _index_by_normalized_path(source_operations)

    public_registry: dict[str, dict[str, Any]] = {}
    for public_operation in public_operations.values():
        lookup_key = (public_operation["method"], _normalize_path(public_operation["path"]))
        source_operation = source_index.get(lookup_key)
        alias_path = PUBLIC_TO_LOCAL_ALIASES.get((public_operation["method"], public_operation["path"]))
        if alias_path:
            source_operation = source_index.get((public_operation["method"], _normalize_path(alias_path))) or source_operation

        operation = dict(public_operation)
        operation["source_key"] = source_operation["key"] if source_operation else None
        operation["generated_from_public_docs"] = True
        public_registry[operation["key"]] = operation

    return public_registry


def generate_module(source_swagger: dict[str, Any], public_spec: dict[str, Any]) -> str:
    operations = generate_operations(source_swagger, public_spec)
    title = (public_spec.get("info") or {}).get("title", "ScyllaDB Cloud API")
    version = (public_spec.get("info") or {}).get("version", "")
    servers = public_spec.get("servers") or []
    base_url = servers[0].get("url") if servers else "https://api.cloud.scylladb.com"
    definitions = source_swagger.get("definitions") or {}
    components = (public_spec.get("components") or {}).get("schemas") or {}

    return (
        '"""Generated ScyllaDB Cloud API request metadata.\n\n'
        "Generated by scylladb_cloud_client.generate. Do not edit by hand.\n"
        f"Whitelist source: {PUBLIC_DOCS_URL}\n"
        '"""\n\n'
        f"API_TITLE = {title!r}\n"
        f"API_VERSION = {version!r}\n"
        f"BASE_URL = {base_url!r}\n"
        f"PUBLIC_DOCS_URL = {PUBLIC_DOCS_URL!r}\n\n"
        f"DEFINITIONS = {pformat(definitions, width=120, sort_dicts=True)}\n\n"
        f"COMPONENTS = {pformat(components, width=120, sort_dicts=True)}\n\n"
        f"OPERATION_REGISTRY = {pformat(operations, width=120, sort_dicts=True)}\n"
    )


def write_generated_module(
    swagger_path: str = DEFAULT_SWAGGER_PATH,
    whitelist: str = DEFAULT_PUBLIC_SPEC_URL,
    output_path: str = DEFAULT_OUTPUT_PATH,
) -> Path:
    source_swagger = _load_json(swagger_path)
    public_spec = _load_json(whitelist)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generate_module(source_swagger, public_spec), encoding="utf-8")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate ScyllaDB Cloud public API operation metadata")
    parser.add_argument("--swagger", default=DEFAULT_SWAGGER_PATH, help="Source Swagger JSON path")
    parser.add_argument("--whitelist", default=DEFAULT_PUBLIC_SPEC_URL, help="Public OpenAPI whitelist path or URL")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH, help="Generated Python module path")
    args = parser.parse_args(argv)

    output = write_generated_module(args.swagger, args.whitelist, args.output)
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
