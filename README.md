scylladb-cloud-client
=====================

Python client and CLI for the public ScyllaDB Cloud API documented at
https://cloud.docs.scylladb.com/stable/api.html.

The generated operation registry is built from the local Swagger file at
`../siren/restapi/docs/swagger.json` and filtered through the
public documentation Swagger whitelist. The CLI refuses operations that are not
present in the public documentation.

Installation
------------

The installer creates a private virtualenv at
`<prefix>/lib/scylladb-cloud-client` and symlinks both `scylladb-cloud-client`
and `scc` into `<prefix>/bin`.

Unless you run as root, the installer refuses to touch paths under `PREFIX`
that already exist but are not owned by you (so a normal user does not
overwrite root-owned `/usr/local` by mistake). For a system-wide install under
`/usr/local`, use `sudo ./install.sh`.

Install to `/usr/local`:

```sh
./install.sh
```

Install to another prefix:

```sh
./install.sh "$HOME/.local"
```

Uninstall from `/usr/local`:

```sh
./uninstall.sh
```

Uninstall from another prefix:

```sh
./uninstall.sh "$HOME/.local"
```

Usage
-----

For authenticated operations, set a token using `SCYLLA_CLOUD_API_KEY` or
`SCYLLA_CLOUD_API_TOKEN`, or pass `--token`. Public operations marked as not
requiring authentication can be called without a token.

List supported public operations:

```sh
scylladb-cloud-client operations list
scc operations list
```

Show operation metadata:

```sh
scylladb-cloud-client operations show GET /account/default
```

Run a documented operation:

```sh
scylladb-cloud-client request GET /account/default
```

Use curated wrappers for common operations:

```sh
scylladb-cloud-client account show
scylladb-cloud-client clusters list --account-id 123 --enriched
scylladb-cloud-client clusters get --account-id 123 --cluster-id 456
scylladb-cloud-client requests get --account-id 123 --request-id 789
scylladb-cloud-client deployment providers
scylladb-cloud-client deployment regions --provider-id 1
scylladb-cloud-client deployment instances --provider-id 1 --region-id 1
scylladb-cloud-client deployment versions
```

Create a cluster from a JSON request body. Replace the example IDs and version
with values from the deployment catalog commands above:

```json
{
  "clusterName": "example-cluster",
  "cloudProviderId": 1,
  "regionId": 1,
  "instanceId": 182,
  "numberOfNodes": 3,
  "scyllaVersion": "2026.1.2",
  "cidrBlock": "10.0.0.0/24",
  "broadcastType": "PRIVATE",
  "replicationFactor": 3,
  "enableDnsAssociation": true,
  "freeTier": false,
  "promProxy": false,
  "userApiInterface": "CQL",
  "provisioning": "dedicated-vm"
}
```

Save the payload to `cluster-create.json`, then run:

```sh
scylladb-cloud-client clusters create \
  --account-id 123 \
  --body-file cluster-create.json \
  --yes
```

Delete a cluster by confirming both the cluster ID and name:

```sh
scylladb-cloud-client clusters delete \
  --account-id 123 \
  --cluster-id 456 \
  --cluster-name example-cluster \
  --yes
```

Pass path and query parameters:

```sh
scylladb-cloud-client request \
  GET '/account/{accountId}/clusters' \
  --path-param accountId=123 \
  --query enriched=true
```

Destructive methods (`POST`, `PUT`, `PATCH`, and `DELETE`) require `--yes`.
Curated cluster creation and deletion commands also require `--yes`.

Regenerating Operations
-----------------------

```sh
python -m scylladb_cloud_client.generate \
  --swagger ../siren/restapi/docs/swagger.json \
  --whitelist https://cloud.docs.scylladb.com/stable/_static/swagger.json
```
