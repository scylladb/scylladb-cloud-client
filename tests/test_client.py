import unittest
from unittest.mock import patch

from scylladb_cloud_client.client import (
    DEFAULT_USER_AGENT,
    ScyllaDBCloudAPIError,
    ScyllaDBCloudClient,
    validate_operation_input,
)
from scylladb_cloud_client.operations import OPERATION_REGISTRY


class FakeResponse:
    status = 200
    headers: dict[str, str] = {}

    def __init__(self, body: bytes = b'{"ok": true}'):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.body


class OperationRegistryTests(unittest.TestCase):
    def test_registry_contains_only_public_documented_operations(self):
        self.assertGreaterEqual(len(OPERATION_REGISTRY), 3)
        self.assertIn("GET /account/default", OPERATION_REGISTRY)
        self.assertIn("POST /pricing", OPERATION_REGISTRY)
        self.assertIn("GET /account/{accountId}/clusters", OPERATION_REGISTRY)
        self.assertNotIn("POST /account/{accountID}/cluster/{clusterID}/reboot/enabled", OPERATION_REGISTRY)

    def test_public_alias_keeps_local_source_key(self):
        operation = OPERATION_REGISTRY["GET /account/{accountId}/clusters"]
        self.assertEqual(operation["path"], "/account/{accountId}/clusters")
        self.assertEqual(operation["source_key"], "GET /account/{account}/cluster")


class ValidationTests(unittest.TestCase):
    def test_path_and_query_parameters_are_coerced(self):
        operation = OPERATION_REGISTRY["GET /account/{accountId}/clusters"]
        path_params, query, body = validate_operation_input(
            operation,
            path_params={"accountId": "123"},
            query={"enriched": "true", "metrics": "NODES_UP,STORAGE_USED"},
        )

        self.assertEqual(path_params, {"accountId": 123})
        self.assertEqual(query, {"enriched": True, "metrics": ["NODES_UP", "STORAGE_USED"]})
        self.assertIsNone(body)

    def test_unsupported_query_parameter_fails(self):
        operation = OPERATION_REGISTRY["GET /account/default"]

        with self.assertRaises(ScyllaDBCloudAPIError):
            validate_operation_input(operation, query={"internal": "true"})

    def test_body_is_required_when_schema_is_documented(self):
        operation = OPERATION_REGISTRY["POST /pricing"]

        with self.assertRaises(ScyllaDBCloudAPIError):
            validate_operation_input(operation)

    def test_unsupported_body_field_fails(self):
        operation = OPERATION_REGISTRY["POST /account/{accountId}/cluster"]

        with self.assertRaisesRegex(ScyllaDBCloudAPIError, "Unknown body field"):
            validate_operation_input(
                operation,
                path_params={"accountId": 123},
                body={"clusterName": "example-cluster", "tablets": "enforced"},
            )

    def test_unsupported_body_field_fails_when_additional_properties_is_false(self):
        operation = {
            "path_parameters": [],
            "query_parameters": [],
            "body_schema": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "additionalProperties": False,
            },
        }

        with self.assertRaisesRegex(ScyllaDBCloudAPIError, "Unknown body field"):
            validate_operation_input(operation, body={"name": "cluster", "extra": "value"})


class ClientTests(unittest.TestCase):
    def test_url_uses_public_path_parameter_names(self):
        client = ScyllaDBCloudClient("token")
        url = client._url_for(
            "/account/{accountId}/clusters",
            {"accountId": 123},
            {"enriched": True},
        )

        self.assertEqual(url, "https://api.cloud.scylladb.com/account/123/clusters?enriched=true")

    def test_url_serializes_array_query_parameters_as_comma_separated_values(self):
        client = ScyllaDBCloudClient("token")
        url = client._url_for(
            "/account/{accountId}/clusters",
            {"accountId": 123},
            {"metrics": ["NODES_UP", "STORAGE_USED"]},
        )

        self.assertEqual(url, "https://api.cloud.scylladb.com/account/123/clusters?metrics=NODES_UP,STORAGE_USED")

    def test_client_can_be_constructed_without_token(self):
        with patch.dict("os.environ", {"SCYLLA_CLOUD_API_KEY": "", "SCYLLA_CLOUD_API_TOKEN": ""}):
            client = ScyllaDBCloudClient()

        self.assertIsNone(client.token)

    def test_auth_required_operation_without_token_fails_before_request(self):
        with patch.dict("os.environ", {"SCYLLA_CLOUD_API_KEY": "", "SCYLLA_CLOUD_API_TOKEN": ""}):
            client = ScyllaDBCloudClient()

        with patch("scylladb_cloud_client.client.urlopen") as urlopen_mock:
            with self.assertRaisesRegex(ScyllaDBCloudAPIError, "Missing ScyllaDB Cloud API token"):
                client.execute("GET", "/account/default")

        urlopen_mock.assert_not_called()

    def test_unauthenticated_operation_without_token_does_not_send_authorization_header(self):
        with patch.dict("os.environ", {"SCYLLA_CLOUD_API_KEY": "", "SCYLLA_CLOUD_API_TOKEN": ""}):
            client = ScyllaDBCloudClient()

        with patch("scylladb_cloud_client.client.urlopen", return_value=FakeResponse()) as urlopen_mock:
            client.execute("GET", "/deployment/cloud-providers")

        request = urlopen_mock.call_args.args[0]
        self.assertFalse(request.has_header("Authorization"))

    def test_unauthenticated_operation_with_token_does_not_send_authorization_header(self):
        client = ScyllaDBCloudClient("token")

        with patch("scylladb_cloud_client.client.urlopen", return_value=FakeResponse()) as urlopen_mock:
            client.execute("GET", "/deployment/cloud-providers")

        request = urlopen_mock.call_args.args[0]
        self.assertFalse(request.has_header("Authorization"))

    def test_auth_required_operation_with_token_sends_authorization_header(self):
        client = ScyllaDBCloudClient("token")

        with patch("scylladb_cloud_client.client.urlopen", return_value=FakeResponse()) as urlopen_mock:
            client.execute("GET", "/account/default")

        request = urlopen_mock.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer token")

    def test_request_sends_package_user_agent(self):
        client = ScyllaDBCloudClient("token")

        with patch("scylladb_cloud_client.client.urlopen", return_value=FakeResponse()) as urlopen_mock:
            client.execute("GET", "/account/default")

        request = urlopen_mock.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), DEFAULT_USER_AGENT)

    def test_api_error_response_fails(self):
        client = ScyllaDBCloudClient("token")

        with patch("scylladb_cloud_client.client.urlopen", return_value=FakeResponse(b'{"error": "040701"}')):
            with self.assertRaisesRegex(ScyllaDBCloudAPIError, "040701"):
                client.execute("GET", "/account/default")

    def test_http_base_url_is_rejected(self):
        with self.assertRaisesRegex(ScyllaDBCloudAPIError, "https scheme"):
            ScyllaDBCloudClient("token", base_url="http://api.cloud.scylladb.com")

    def test_https_base_url_is_accepted(self):
        client = ScyllaDBCloudClient("token", base_url="https://example.test:8443/api")
        self.assertEqual(client.base_url, "https://example.test:8443/api")


if __name__ == "__main__":
    unittest.main()
