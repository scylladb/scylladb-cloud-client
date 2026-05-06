"""ScyllaDB Cloud public API client."""

from scylladb_cloud_client.client import (
    DEFAULT_BASE_URL,
    ScyllaDBCloudAPIError,
    ScyllaDBCloudClient,
)

__all__ = [
    "DEFAULT_BASE_URL",
    "ScyllaDBCloudAPIError",
    "ScyllaDBCloudClient",
]
