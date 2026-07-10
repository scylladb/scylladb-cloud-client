import contextlib
import io
import unittest
from unittest.mock import patch

from scylladb_cloud_client import cli


class FakeClient:
    calls = []

    def __init__(self, token, *, base_url, timeout, debug):
        self.token = token
        self.base_url = base_url
        self.timeout = timeout
        self.debug = debug

    def execute(self, method, path, *, path_params=None, query=None, body=None):
        self.calls.append(
            {
                "token": self.token,
                "base_url": self.base_url,
                "timeout": self.timeout,
                "debug": self.debug,
                "method": method,
                "path": path,
                "path_params": path_params,
                "query": query,
                "body": body,
            }
        )
        return {"status": "success", "status_code": 200, "data": {"ok": True}, "headers": {}}


class CliBaseUrlTests(unittest.TestCase):
    def test_http_base_url_is_rejected(self):
        rc = cli.run(["--token", "token-1", "--base-url", "http://api.cloud.scylladb.com", "account", "show"])

        self.assertEqual(rc, 1)


class CuratedCliTests(unittest.TestCase):
    def setUp(self):
        FakeClient.calls = []

    def run_cli(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
            patch.object(cli, "ScyllaDBCloudClient", FakeClient),
        ):
            return cli.run(argv)

    def test_account_show_maps_to_public_default_account_operation(self):
        rc = self.run_cli(["--token", "token-1", "account", "show"])

        self.assertEqual(rc, 0)
        self.assertEqual(FakeClient.calls[0]["method"], "GET")
        self.assertEqual(FakeClient.calls[0]["path"], "/account/default")
        self.assertEqual(FakeClient.calls[0]["path_params"], {})

    def test_clusters_list_maps_friendly_flags_to_public_operation(self):
        rc = self.run_cli(
            [
                "--token",
                "token-1",
                "clusters",
                "list",
                "--account-id",
                "123",
                "--enriched",
                "--metrics",
                "NODES_UP,STORAGE_USED",
            ]
        )

        self.assertEqual(rc, 0)
        self.assertEqual(FakeClient.calls[0]["path"], "/account/{accountId}/clusters")
        self.assertEqual(FakeClient.calls[0]["path_params"], {"accountId": 123})
        self.assertEqual(FakeClient.calls[0]["query"], {"enriched": True, "metrics": "NODES_UP,STORAGE_USED"})

    def test_cluster_delete_requires_confirmation(self):
        rc = self.run_cli(["--token", "token-1", "clusters", "delete", "--account-id", "123", "--cluster-id", "456"])

        self.assertEqual(rc, 1)
        self.assertEqual(FakeClient.calls, [])

    def test_cluster_delete_requires_cluster_name_confirmation(self):
        rc = self.run_cli(
            [
                "--token",
                "token-1",
                "clusters",
                "delete",
                "--account-id",
                "123",
                "--cluster-id",
                "456",
                "--yes",
            ]
        )

        self.assertEqual(rc, 1)
        self.assertEqual(FakeClient.calls, [])

    def test_cluster_delete_with_confirmation_maps_to_public_operation(self):
        rc = self.run_cli(
            [
                "--token",
                "token-1",
                "clusters",
                "delete",
                "--account-id",
                "123",
                "--cluster-id",
                "456",
                "--cluster-name",
                "example-cluster",
                "--yes",
            ]
        )

        self.assertEqual(rc, 0)
        self.assertEqual(FakeClient.calls[0]["method"], "POST")
        self.assertEqual(FakeClient.calls[0]["path"], "/account/{accountId}/cluster/{clusterId}/delete")
        self.assertEqual(FakeClient.calls[0]["path_params"], {"accountId": 123, "clusterId": 456})
        self.assertEqual(FakeClient.calls[0]["body"], {"clusterName": "example-cluster"})

    def test_cluster_create_requires_confirmation(self):
        rc = self.run_cli(
            [
                "--token",
                "token-1",
                "clusters",
                "create",
                "--account-id",
                "123",
                "--body-json",
                '{"clusterName":"test-cluster"}',
            ]
        )

        self.assertEqual(rc, 1)
        self.assertEqual(FakeClient.calls, [])

    def test_cluster_create_with_confirmation_maps_to_public_operation(self):
        rc = self.run_cli(
            [
                "--token",
                "token-1",
                "clusters",
                "create",
                "--account-id",
                "123",
                "--body-json",
                '{"clusterName":"test-cluster"}',
                "--yes",
            ]
        )

        self.assertEqual(rc, 0)
        self.assertEqual(FakeClient.calls[0]["method"], "POST")
        self.assertEqual(FakeClient.calls[0]["path"], "/account/{accountId}/cluster")
        self.assertEqual(FakeClient.calls[0]["path_params"], {"accountId": 123})
        self.assertEqual(FakeClient.calls[0]["body"], {"clusterName": "test-cluster"})

    def test_deployment_instances_maps_to_public_operation(self):
        rc = self.run_cli(
            [
                "--token",
                "token-1",
                "deployment",
                "instances",
                "--provider-id",
                "1",
                "--region-id",
                "2",
                "--target",
                "VECTOR_SEARCH",
            ]
        )

        self.assertEqual(rc, 0)
        self.assertEqual(FakeClient.calls[0]["path"], "/deployment/cloud-provider/{cloudProviderId}/region/{regionId}")
        self.assertEqual(FakeClient.calls[0]["path_params"], {"cloudProviderId": 1, "regionId": 2})
        self.assertEqual(FakeClient.calls[0]["query"], {"target": "VECTOR_SEARCH"})

    def test_generic_request_still_requires_yes_for_destructive_methods(self):
        rc = self.run_cli(
            [
                "--token",
                "token-1",
                "request",
                "POST",
                "/pricing",
                "--body-json",
                '{"infrastructure":{"provider":"AWS"}}',
            ]
        )

        self.assertEqual(rc, 1)
        self.assertEqual(FakeClient.calls, [])


if __name__ == "__main__":
    unittest.main()
