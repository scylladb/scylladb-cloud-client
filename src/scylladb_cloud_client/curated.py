"""Curated wrappers over generated public ScyllaDB Cloud API operations."""

from __future__ import annotations

from typing import Any


class CuratedCommandError(ValueError):
    """Raised when a curated command cannot be mapped to a public operation."""


def _optional_query(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value not in (None, False, [], "")}


def build_curated_request(args: Any) -> dict[str, Any]:
    command = getattr(args, "command", None)

    if command == "account" and getattr(args, "account_command", None) == "show":
        return {
            "method": "GET",
            "path": "/account/default",
            "path_params": {},
            "query": {},
            "body": None,
        }

    if command == "clusters":
        cluster_command = getattr(args, "clusters_command", None)
        account_id = getattr(args, "account_id", None)
        cluster_id = getattr(args, "cluster_id", None)
        if cluster_command == "list":
            return {
                "method": "GET",
                "path": "/account/{accountId}/clusters",
                "path_params": {"accountId": account_id},
                "query": _optional_query(enriched=getattr(args, "enriched", False), metrics=getattr(args, "metrics", None)),
                "body": None,
            }
        if cluster_command == "get":
            return {
                "method": "GET",
                "path": "/account/{accountId}/cluster/{clusterId}",
                "path_params": {"accountId": account_id, "clusterId": cluster_id},
                "query": _optional_query(enriched=getattr(args, "enriched", False)),
                "body": None,
            }
        if cluster_command == "dcs":
            return {
                "method": "GET",
                "path": "/account/{accountId}/cluster/{clusterId}/dcs",
                "path_params": {"accountId": account_id, "clusterId": cluster_id},
                "query": _optional_query(enriched=getattr(args, "enriched", False)),
                "body": None,
            }
        if cluster_command == "nodes":
            return {
                "method": "GET",
                "path": "/account/{accountId}/cluster/{clusterId}/nodes",
                "path_params": {"accountId": account_id, "clusterId": cluster_id},
                "query": _optional_query(enriched=getattr(args, "enriched", False)),
                "body": None,
            }
        if cluster_command == "create":
            if not getattr(args, "yes", False):
                raise CuratedCommandError("Cluster create requires --yes")
            return {
                "method": "POST",
                "path": "/account/{accountId}/cluster",
                "path_params": {"accountId": account_id},
                "query": {},
                "body": getattr(args, "body", None),
            }
        if cluster_command == "delete":
            if not getattr(args, "yes", False):
                raise CuratedCommandError("Cluster delete requires --yes")
            cluster_name = getattr(args, "cluster_name", None)
            if not cluster_name:
                raise CuratedCommandError("Cluster delete requires --cluster-name")
            return {
                "method": "POST",
                "path": "/account/{accountId}/cluster/{clusterId}/delete",
                "path_params": {"accountId": account_id, "clusterId": cluster_id},
                "query": {},
                "body": {"clusterName": cluster_name},
            }

    if command == "requests":
        requests_command = getattr(args, "requests_command", None)
        account_id = getattr(args, "account_id", None)
        if requests_command == "get":
            return {
                "method": "GET",
                "path": "/account/{accountId}/cluster/request/{requestId}",
                "path_params": {"accountId": account_id, "requestId": getattr(args, "request_id", None)},
                "query": {},
                "body": None,
            }
        if requests_command == "list":
            return {
                "method": "GET",
                "path": "/account/{accountId}/cluster/{clusterId}/request",
                "path_params": {"accountId": account_id, "clusterId": getattr(args, "cluster_id", None)},
                "query": _optional_query(type=getattr(args, "type", None), status=getattr(args, "status", None)),
                "body": None,
            }

    if command == "deployment":
        deployment_command = getattr(args, "deployment_command", None)
        if deployment_command == "providers":
            return {
                "method": "GET",
                "path": "/deployment/cloud-providers",
                "path_params": {},
                "query": {},
                "body": None,
            }
        if deployment_command == "regions":
            return {
                "method": "GET",
                "path": "/deployment/cloud-provider/{cloudProviderId}/regions",
                "path_params": {"cloudProviderId": getattr(args, "provider_id", None)},
                "query": _optional_query(defaults=getattr(args, "defaults", False)),
                "body": None,
            }
        if deployment_command == "instances":
            return {
                "method": "GET",
                "path": "/deployment/cloud-provider/{cloudProviderId}/region/{regionId}",
                "path_params": {
                    "cloudProviderId": getattr(args, "provider_id", None),
                    "regionId": getattr(args, "region_id", None),
                },
                "query": _optional_query(
                    defaults=getattr(args, "defaults", False),
                    target=getattr(args, "target", None),
                ),
                "body": None,
            }
        if deployment_command == "versions":
            return {
                "method": "GET",
                "path": "/deployment/scylla-versions",
                "path_params": {},
                "query": _optional_query(defaults=getattr(args, "defaults", False)),
                "body": None,
            }

    raise CuratedCommandError(f"Unsupported curated ScyllaDB Cloud API command: {command}")
