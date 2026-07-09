#!/usr/bin/env bash
# =============================================================================
# Unity Catalog bootstrap (idempotent).
#
# Creates the UC objects that back the medallion lakehouse:
#   - storage credential   (from the Phase-1 access connector)
#   - external locations   (one per ADLS container)
#   - catalog + schemas    (bronze/silver/gold -> own container; ops -> default)
#
# These are Databricks *metastore* objects (not Azure), so we manage them with
# the Databricks CLI rather than Terraform. Zero compute cost — control-plane
# API calls only.
#
# Auth: uses the databricks-pat stored in Key Vault (workspace-admin token).
# Prereqs: az CLI logged in; databricks CLI installed; Phase 1 applied.
#
# Usage (Git Bash / WSL):
#   ./setup_uc.sh
# =============================================================================
set -uo pipefail

# ---- config (override via env) ---------------------------------------------
: "${WORKSPACE_URL:=https://adb-7405608693609813.13.azuredatabricks.net}"
: "${KEY_VAULT:=ghan-dev-kv-a5k8k}"
: "${STORAGE_ACCOUNT:=ghanalyticsdeva5k8k}"
: "${RESOURCE_GROUP:=rg-ghanalytics-dev}"
: "${ACCESS_CONNECTOR:=ghan-dev-dbw-ac}"
: "${CATALOG:=gh_analytics_dev}"
: "${CRED_NAME:=ghan_dev_adls_cred}"
: "${EL_PREFIX:=ghan_dev}"
CONTAINERS=(landing bronze silver gold checkpoints quarantine)
LAYER_SCHEMAS=(bronze silver gold)

export DATABRICKS_HOST="$WORKSPACE_URL"
export DATABRICKS_TOKEN="$(az keyvault secret show --vault-name "$KEY_VAULT" --name databricks-pat --query value -o tsv)"
[ -n "$DATABRICKS_TOKEN" ] || { echo "ERROR: could not read databricks-pat from $KEY_VAULT"; exit 1; }

abfss() { echo "abfss://$1@${STORAGE_ACCOUNT}.dfs.core.windows.net/${2:-}"; }

# create helper: tolerate "already exists" so the script is re-runnable
create() { # $1 = human label, rest = databricks command
  local label="$1"; shift
  local out; out="$("$@" 2>&1)"
  if echo "$out" | grep -qiE '"(name|full_name)"'; then echo "  [OK]      $label"
  elif echo "$out" | grep -qiE 'already exists|EXISTS'; then echo "  [EXISTS]  $label"
  else echo "  [ERROR]   $label -> $(echo "$out" | head -1)"; fi
}

echo "== 1. Storage credential =="
AC_ID="$(az resource show -g "$RESOURCE_GROUP" -n "$ACCESS_CONNECTOR" \
  --resource-type Microsoft.Databricks/accessConnectors --query id -o tsv)"
create "$CRED_NAME" databricks storage-credentials create --json \
  "{\"name\":\"$CRED_NAME\",\"comment\":\"MI access to $STORAGE_ACCOUNT\",\"azure_managed_identity\":{\"access_connector_id\":\"$AC_ID\"}}"

echo "== 2. External locations =="
for c in "${CONTAINERS[@]}"; do
  create "${EL_PREFIX}_${c}" databricks external-locations create --json \
    "{\"name\":\"${EL_PREFIX}_${c}\",\"url\":\"$(abfss "$c")\",\"credential_name\":\"$CRED_NAME\"}"
done

echo "== 3. Catalog =="
create "$CATALOG" databricks catalogs create --json \
  "{\"name\":\"$CATALOG\",\"storage_root\":\"$(abfss checkpoints _uc_catalog)\",\"comment\":\"GH Analytics medallion catalog\"}"

echo "== 4. Schemas =="
for s in "${LAYER_SCHEMAS[@]}"; do
  create "$CATALOG.$s" databricks schemas create --json \
    "{\"catalog_name\":\"$CATALOG\",\"name\":\"$s\",\"storage_root\":\"$(abfss "$s")\",\"comment\":\"$s layer\"}"
done
create "$CATALOG.ops" databricks schemas create --json \
  "{\"catalog_name\":\"$CATALOG\",\"name\":\"ops\",\"comment\":\"operational: dq_results, audit, lineage\"}"

echo "== Done. Verify: =="
databricks schemas list "$CATALOG" 2>/dev/null | head -20
