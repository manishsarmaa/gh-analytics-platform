# Runbook

Operational guide: how to run, recover, and reason about cost.

## Common operations

### Trigger a batch hour manually (what the hourly trigger does)
```bash
export DATABRICKS_HOST=https://adb-7405608693609813.13.azuredatabricks.net
export DATABRICKS_TOKEN="$(az keyvault secret show --vault-name ghan-dev-kv-a5k8k --name databricks-pat --query value -o tsv)"
databricks jobs run-now --json '{"job_id":304513597804481,"job_parameters":{"env":"dev","execution_date":"2024-01-15","landing_path":"abfss://landing@ghanalyticsdeva5k8k.dfs.core.windows.net/gharchive/year=2024/month=01/day=15/hour=00/","source_file":"2024-01-15-0.json.gz"}}'
```
Or run `pl_hourly_ingestion` in ADF Studio (Debug) — it also does the Copy.

### Backfill a range
Run `pl_backfill_historical` (ADF) with `start_date`/`end_date`/`start_hour`/`end_hour`.
Parallelism = ForEach `batchCount` (≤ job `max_concurrent_runs`=5). Idempotent, so a
partial failure is safe to re-run.

### Enrichment / maintenance / streaming
```bash
databricks jobs run-now --json '{"job_id":544994714197226,"job_parameters":{"env":"dev","batch_size":"100"}}'  # repo metadata
databricks jobs run-now --json '{"job_id":683550268106263,"job_parameters":{"env":"dev","vacuum_retention_hours":"168"}}'  # maintenance
# streaming: seed with the producer, then run gh_streaming_ingestion (availableNow)
PYTHONPATH=src EVENTHUB_CONN="$(az keyvault secret show --vault-name ghan-dev-kv-a5k8k --name eventhub-connection-string --query value -o tsv)" \
  .venv/Scripts/python.exe -m streaming.eventhub_producer --iterations 3
```

## Common failures

| Symptom | Cause | Fix |
|---|---|---|
| Cluster `CLOUD_PROVIDER_RESOURCE_STOCKOUT` | Classic VM unavailable (4-vCPU trial cap) | Use serverless (already the default). |
| `NOT_SUPPORTED_WITH_SERVERLESS: PERSIST` | `.cache()`/GX-Spark on serverless | Remove cache; GX runs on a pandas sample. |
| `ModuleNotFoundError: yaml` on serverless | pyyaml not in base env | Add to the job `environments` deps. |
| Enrichment writes 0 rows | Target repos are deleted spam (404) | Ranking is by distinct actors (already spam-resistant). |
| ADF `InvalidTemplate: result_state` | polling before run terminal | Guarded with `contains()` in the poll expression. |
| Backfill task fails on Delta conflict | same-day parallel writes | Idempotent + task `max_retries=2`; re-run the backfill. |
| ADF pipelines missing after `terraform apply` | TF reverted the Studio Git link | Re-link ADF Studio → Git (`/adf`); see below. |

## Re-link ADF to Git
`terraform apply` reverts the Studio-set Git connection (the TF `azurerm_data_factory`
has no `github_configuration`). To restore: ADF Studio → **Manage → Git configuration
→ Configure** → GitHub `manishsarmaa/gh-analytics-platform`, collaboration branch
`main`, root folder `/adf`, import existing. Pipelines/triggers reappear from `/adf`.

## DQ / observability
- `ops.dq_results` — per-check pass/fail (custom full-table + GX sample).
- A **critical** custom check failing raises → the DQ task fails → the medallion
  job fails → ADF marks the run failed (alerting hook).
- Databricks SQL queries: `dashboards/databricks_sql/operational_queries.sql`.

## Cost (dev, approximate — 30-day trial)

| Resource | Idle | Notes |
|---|---|---|
| ADLS Gen2 | ~₹0 | pennies/GB stored |
| Key Vault, RG, RBAC, MI | Free | |
| ADF | ~₹0 at rest | ~₹0.85 / 1,000 activity runs |
| Databricks workspace | **Free** | pay only for compute |
| Serverless job (per medallion run) | ~₹5–15 | ~2–5 min; the main run cost |
| Event Hubs **Standard** | ~₹2–3/hr | only tier with Kafka; **revert to Basic to stop** when not streaming |
| SQL Warehouse (serverless) | ~₹0 idle | auto-stops; per-second when querying |

**Levers:** serverless (no idle VM); job clusters not interactive; `availableNow`
streaming (not continuous); `terraform destroy` between sessions. The dominant
avoidable cost is **Event Hubs Standard** — drop to Basic when not demoing streaming.
