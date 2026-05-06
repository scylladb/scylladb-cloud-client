"""Command line interface for the ScyllaDB Cloud public API client."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Mapping

from scylladb_cloud_client.client import ScyllaDBCloudAPIError, ScyllaDBCloudClient
from scylladb_cloud_client.curated import CuratedCommandError, build_curated_request
from scylladb_cloud_client.operations import OPERATION_REGISTRY, PUBLIC_DOCS_URL

_DESTRUCTIVE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_CURATED_COMMANDS = {"account", "clusters", "requests", "deployment"}


def _load_json_body_arg(body_json: str | None = None, body_file: str | None = None) -> Any:
    if body_json and body_file:
        raise ScyllaDBCloudAPIError("Use either --body-json or --body-file, not both")
    if body_json:
        try:
            return json.loads(body_json)
        except json.JSONDecodeError as exc:
            raise ScyllaDBCloudAPIError(f"Invalid --body-json: {exc}") from exc
    if body_file:
        try:
            with open(body_file, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except OSError as exc:
            raise ScyllaDBCloudAPIError(f"Unable to read --body-file {body_file}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ScyllaDBCloudAPIError(f"Invalid JSON in --body-file {body_file}: {exc}") from exc
    return None


def _parse_key_value_items(items: list[str] | None, option_name: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for item in items or []:
        if "=" not in item:
            raise ScyllaDBCloudAPIError(f"{option_name} must use KEY=VALUE format: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ScyllaDBCloudAPIError(f"{option_name} key cannot be empty: {item}")
        if option_name == "--query" and key in parsed:
            if not isinstance(parsed[key], list):
                parsed[key] = [parsed[key]]
            parsed[key].append(value)
        else:
            parsed[key] = value
    return parsed


def _format_json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def _format_table(rows: list[list[Any]], headers: list[str]) -> str:
    values = [headers] + [[str(value) for value in row] for row in rows]
    widths = [max(len(row[index]) for row in values) for index in range(len(headers))]
    lines = [
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(values[0])),
        "  ".join("-" * width for width in widths),
    ]
    lines.extend("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)) for row in values[1:])
    return "\n".join(lines)


def _format_data_table(data: Any) -> str:
    if isinstance(data, list):
        if data and all(isinstance(item, Mapping) for item in data):
            keys = sorted({key for item in data for key in item.keys()})
            return _format_table([[item.get(key, "") for key in keys] for item in data], keys)
        return "\n".join(str(item) for item in data)
    if isinstance(data, Mapping):
        rows = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, default=str)
            rows.append([key, value])
        return _format_table(rows, ["Field", "Value"])
    return str(data)


def _format_result_data(data: Any, output_format: str) -> str:
    if output_format == "json":
        return _format_json(data)
    if output_format == "table":
        return _format_data_table(data)
    if isinstance(data, str):
        return data
    return _format_json(data)


def _operation_matches(operation: Mapping[str, Any], tag: str | None = None, method: str | None = None) -> bool:
    if method and operation["method"] != method.upper():
        return False
    if tag and tag not in operation.get("tags", []):
        return False
    return True


def _print_operations_list(tag: str | None = None, method: str | None = None) -> int:
    rows = []
    for operation in sorted(OPERATION_REGISTRY.values(), key=lambda item: item["key"]):
        if _operation_matches(operation, tag=tag, method=method):
            rows.append(
                [
                    operation["method"],
                    operation["path"],
                    ", ".join(operation.get("tags") or []),
                    operation.get("summary", ""),
                ]
            )
    print(_format_table(rows, ["Method", "Path", "Tags", "Summary"]))
    return 0


def _print_operation_show(method: str, path: str) -> int:
    key = f"{method.upper()} {path}"
    operation = OPERATION_REGISTRY.get(key)
    if operation is None:
        raise ScyllaDBCloudAPIError(f"Unsupported public ScyllaDB Cloud API operation: {key}")
    print(_format_json(operation))
    return 0


def _add_account_id_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--account-id", type=int, required=True, help="Account ID")


def _add_cluster_id_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cluster-id", type=int, required=True, help="Cluster ID")


def _add_body_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--body-json", help="JSON request body")
    parser.add_argument("--body-file", help="Path to JSON request body file")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scylladb-cloud-client",
        description=f"CLI for ScyllaDB Cloud public API operations documented at {PUBLIC_DOCS_URL}",
    )
    parser.add_argument("--api-key", dest="token", help="ScyllaDB Cloud API key")
    parser.add_argument("--token", dest="token", help="ScyllaDB Cloud API token")
    parser.add_argument(
        "--base-url",
        default="https://api.cloud.scylladb.com",
        help="API base URL (https only; http is rejected)",
    )
    parser.add_argument("--output", "-o", choices=("json", "table", "text"), default="json", help="Output format")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    parser.add_argument("--debug", "-d", action="store_true", help="Print request and response debug details")

    subparsers = parser.add_subparsers(dest="command", required=True)

    account = subparsers.add_parser("account", help="Account operations")
    account_subparsers = account.add_subparsers(dest="account_command", required=True)
    account_subparsers.add_parser("show", help="Show the default account")

    clusters = subparsers.add_parser("clusters", help="Cluster operations")
    clusters_subparsers = clusters.add_subparsers(dest="clusters_command", required=True)
    clusters_list = clusters_subparsers.add_parser("list", help="List clusters in an account")
    _add_account_id_arg(clusters_list)
    clusters_list.add_argument("--enriched", action="store_true", help="Include provider, region, and instance data")
    clusters_list.add_argument("--metrics", help="Comma-separated metrics to fetch")
    clusters_get = clusters_subparsers.add_parser("get", help="Get cluster details")
    _add_account_id_arg(clusters_get)
    _add_cluster_id_arg(clusters_get)
    clusters_get.add_argument("--enriched", action="store_true", help="Include provider, region, and instance data")
    clusters_dcs = clusters_subparsers.add_parser("dcs", help="List cluster datacenters")
    _add_account_id_arg(clusters_dcs)
    _add_cluster_id_arg(clusters_dcs)
    clusters_dcs.add_argument("--enriched", action="store_true", help="Include provider and region data")
    clusters_nodes = clusters_subparsers.add_parser("nodes", help="List cluster nodes")
    _add_account_id_arg(clusters_nodes)
    _add_cluster_id_arg(clusters_nodes)
    clusters_nodes.add_argument("--enriched", action="store_true", help="Include additional node data")
    clusters_create = clusters_subparsers.add_parser("create", help="Create a cluster")
    _add_account_id_arg(clusters_create)
    _add_body_args(clusters_create)
    clusters_create.add_argument("--yes", action="store_true", help="Confirm cluster creation")
    clusters_delete = clusters_subparsers.add_parser("delete", help="Delete a cluster")
    _add_account_id_arg(clusters_delete)
    _add_cluster_id_arg(clusters_delete)
    clusters_delete.add_argument("--cluster-name", help="Cluster name confirmation payload")
    clusters_delete.add_argument("--yes", action="store_true", help="Confirm cluster deletion")

    requests = subparsers.add_parser("requests", help="Cluster request operations")
    requests_subparsers = requests.add_subparsers(dest="requests_command", required=True)
    requests_get = requests_subparsers.add_parser("get", help="Get a cluster request")
    _add_account_id_arg(requests_get)
    requests_get.add_argument("--request-id", type=int, required=True, help="Request ID")
    requests_list = requests_subparsers.add_parser("list", help="List cluster requests")
    _add_account_id_arg(requests_list)
    _add_cluster_id_arg(requests_list)
    requests_list.add_argument("--type", help="Request type filter")
    requests_list.add_argument("--status", help="Request status filter")

    deployment = subparsers.add_parser("deployment", help="Deployment catalog operations")
    deployment_subparsers = deployment.add_subparsers(dest="deployment_command", required=True)
    deployment_subparsers.add_parser("providers", help="List supported cloud providers")
    deployment_regions = deployment_subparsers.add_parser("regions", help="List supported regions for a provider")
    deployment_regions.add_argument("--provider-id", type=int, required=True, help="Cloud provider ID")
    deployment_regions.add_argument("--defaults", action="store_true", help="Include default deployment data")
    deployment_instances = deployment_subparsers.add_parser("instances", help="List supported instances for a region")
    deployment_instances.add_argument("--provider-id", type=int, required=True, help="Cloud provider ID")
    deployment_instances.add_argument("--region-id", type=int, required=True, help="Cloud provider region ID")
    deployment_instances.add_argument("--defaults", action="store_true", help="Include default deployment data")
    deployment_instances.add_argument("--target", help="Optional target filter, e.g. VECTOR_SEARCH")
    deployment_versions = deployment_subparsers.add_parser("versions", help="List supported ScyllaDB Cloud versions")
    deployment_versions.add_argument("--defaults", action="store_true", help="Include default version data")

    operations = subparsers.add_parser("operations", help="List or inspect supported public operations")
    operations_subparsers = operations.add_subparsers(dest="operations_command", required=True)
    operations_list = operations_subparsers.add_parser("list", help="List supported operations")
    operations_list.add_argument("--tag", help="Filter by exact tag")
    operations_list.add_argument("--method", help="Filter by HTTP method")
    operations_show = operations_subparsers.add_parser("show", help="Show generated metadata for one operation")
    operations_show.add_argument("method", help="HTTP method")
    operations_show.add_argument("path", help="Documented API path, e.g. /account/default")

    request = subparsers.add_parser("request", help="Execute a supported public API operation")
    request.add_argument("method", help="HTTP method")
    request.add_argument("path", help="Documented API path")
    request.add_argument("--path-param", action="append", default=[], help="Path parameter as KEY=VALUE")
    request.add_argument("--query", action="append", default=[], help="Query parameter as KEY=VALUE")
    request.add_argument("--body-json", help="JSON request body")
    request.add_argument("--body-file", help="Path to JSON request body file")
    request.add_argument("--yes", action="store_true", help="Confirm POST/PUT/PATCH/DELETE requests")
    return parser


def run(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "operations":
            if args.operations_command == "list":
                return _print_operations_list(tag=getattr(args, "tag", None), method=getattr(args, "method", None))
            return _print_operation_show(args.method, args.path)

        if args.command == "request":
            if args.method.upper() in _DESTRUCTIVE_METHODS and not args.yes:
                raise ScyllaDBCloudAPIError(f"Destructive operation {args.method.upper()} {args.path} requires --yes")
            request = {
                "method": args.method,
                "path": args.path,
                "path_params": _parse_key_value_items(args.path_param, "--path-param"),
                "query": _parse_key_value_items(args.query, "--query"),
                "body": _load_json_body_arg(args.body_json, args.body_file),
            }
        elif args.command in _CURATED_COMMANDS:
            if hasattr(args, "body_json") or hasattr(args, "body_file"):
                args.body = _load_json_body_arg(getattr(args, "body_json", None), getattr(args, "body_file", None))
            request = build_curated_request(args)
        else:
            raise ScyllaDBCloudAPIError(f"Unsupported command: {args.command}")

        client = ScyllaDBCloudClient(
            args.token,
            base_url=args.base_url,
            timeout=args.timeout,
            debug=args.debug,
        )
        result = client.execute(
            request["method"],
            request["path"],
            path_params=request.get("path_params"),
            query=request.get("query"),
            body=request.get("body"),
        )
        print(_format_result_data(result["data"], args.output))
        return 0
    except (CuratedCommandError, ScyllaDBCloudAPIError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
