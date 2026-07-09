# Databricks Setup (Phase 2)

Databricks-side configuration: Unity Catalog objects, the compute cluster
policy, the KV-backed secret scope, and the Asset Bundle.

> Split of tools: **Terraform** = Azure resources · **Databricks CLI** = metastore
> objects (UC, policies, scopes) · **Asset Bundle** = notebooks + jobs.

## 1. Unity Catalog — `setup_uc.sh`

Idempotent bootstrap of the storage credential, external locations, catalog,
and schemas. Already applied to dev. Re-run any time:

```bash
cd infra/databricks
./setup_uc.sh            # Git Bash / WSL; reads databricks-pat from Key Vault
```

Result: catalog `gh_analytics_dev` with schemas `bronze`/`silver`/`gold`
(each managed in its own ADLS container) and `ops` (catalog-default storage).

## 2. Cluster policy — `cluster-policy.json`

`gh-analytics-job-policy` (id `00195EEF89A45D23`) enforces the cost controls:
single-node, spot-with-fallback, 10–30 min auto-terminate, DBR 15.4 LTS,
UC single-user mode. Recreate from the definition:

```bash
databricks cluster-policies create --json \
  "$(python -c "import json;print(json.dumps({'name':'gh-analytics-job-policy','definition':open('cluster-policy.json').read()}))")"
```

ADF job clusters (Phase 5) and DAB jobs reference this `policy_id`.

## 3. KV-backed secret scope — **manual (needs Azure AD auth)**

Azure Key Vault-backed scopes **cannot be created with a PAT** — Databricks
requires an interactive Azure AD token. Two prerequisites are already handled:
- Terraform grants the first-party *AzureDatabricks* SP `Key Vault Secrets User`
  on the vault (re-apply Phase 1 to add it).
- Secrets exist in `ghan-dev-kv-a5k8k`: `github-pat`, `databricks-pat`,
  `eventhub-connection-string`.

Create the scope via the workspace UI (fastest):

1. Open: `https://adb-7405608693609813.13.azuredatabricks.net/#secrets/createScope`
2. Fill in:
   - **Scope Name**: `gh-analytics-kv`
   - **Manage Principal**: All Users
   - **DNS Name**: `https://ghan-dev-kv-a5k8k.vault.azure.net/`
   - **Resource ID**: `/subscriptions/d5f98fab-893f-45ce-9fdc-c3399ba9f46f/resourceGroups/rg-ghanalytics-dev/providers/Microsoft.KeyVault/vaults/ghan-dev-kv-a5k8k`
3. **Create**, then verify:
   ```bash
   databricks secrets list-scopes
   databricks secrets list-secrets gh-analytics-kv
   ```

Notebooks then read secrets with `dbutils.secrets.get("gh-analytics-kv", "github-pat")`.

## 4. Asset Bundle — `../../databricks.yml`

Bundle root is the repo root (so notebooks can import `src/` modules). Deploy:

```bash
export DATABRICKS_HOST=https://adb-7405608693609813.13.azuredatabricks.net
export DATABRICKS_TOKEN="$(az keyvault secret show --vault-name ghan-dev-kv-a5k8k --name databricks-pat --query value -o tsv)"
databricks bundle validate -t dev
databricks bundle deploy   -t dev
```

Jobs (streaming, optimization) are added to the bundle in later phases as their
notebooks are written.
