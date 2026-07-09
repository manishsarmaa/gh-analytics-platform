# CLAUDE.md — GH Ecosystem Analytics Platform

Production-grade Azure data-engineering platform: ingest GitHub public events
(GH Archive + GitHub API), process through a medallion lakehouse (Delta on
Databricks / Unity Catalog), serve analytics. **ADF orchestrates batch; a
Databricks serverless job does the compute.**

## Architecture (as built)

```
GH Archive .json.gz ──(ADF Copy)──▶ ADLS landing
                                      │
        ADF pl_hourly_ingestion ──(Web Activity: Jobs API run-now)──▶
                                      │
      Databricks serverless job "gh_medallion_batch" (multi-task):
        bronze ─▶ silver ─▶ gold   (+ per-layer DQ tasks)
                                      │
                              UC managed Delta tables in ADLS
                              gh_analytics_dev.{bronze,silver,gold,ops}
```

**Key decision:** batch runs on **Databricks serverless**, not classic clusters
(the Azure trial is capped at 4 regional vCPUs + stockouts). ADF triggers the
serverless job via the Jobs API using its **managed identity** (no secrets).
See `memory/compute-strategy-serverless.md`.

## Environment / resources (dev)

| Thing | Value |
|---|---|
| Subscription | `d5f98fab-893f-45ce-9fdc-c3399ba9f46f` · region `centralindia` |
| Resource group | `rg-ghanalytics-dev` |
| Storage (ADLS) | `ghanalyticsdeva5k8k` — containers: landing/bronze/silver/gold/checkpoints/quarantine |
| Key Vault | `ghan-dev-kv-a5k8k` (secrets: github-pat, databricks-pat, eventhub-connection-string) |
| Databricks | `https://adb-7405608693609813.13.azuredatabricks.net` (Premium, Unity Catalog) |
| UC catalog | `gh_analytics_dev` (schemas: bronze/silver/gold/ops) |
| Medallion job id | `304513597804481` (`[dev] gh-medallion-batch`) |
| ADF | `ghan-dev-adf-a5k8k` (MI appId `8639ef75-b8bd-4223-ad30-e835f82863d7`, CAN_MANAGE_RUN on the job) |
| Event Hubs | `ghan-dev-ehns-a5k8k` / hub `gh-events` (Basic, $Default CG) |

All non-secret config lives in `configs/dev.yaml`; secrets only in Key Vault.

## Layout

- `infra/terraform/` — Azure resources (RG, ADLS, KV, Event Hubs, ADF, Databricks, RBAC). Remote state; run via `bootstrap/bootstrap-state.ps1` then `terraform`.
- `infra/databricks/` — `setup_uc.sh` (UC objects), `cluster-policy.json`, README (secret-scope UI step).
- `databricks.yml` — DAB (bundle root = repo root); syncs `src/`+`configs`; defines the serverless medallion job.
- `src/transformations/` — pure PySpark functions (unit-tested). `src/notebooks/` — Databricks notebooks (thin I/O wrappers). `src/dq/` — DQ runner. `src/utils/` — config + logging.
- `adf/` — ADF pipelines/datasets/linked services as JSON (Git-integrated Studio, root folder `/adf`).
- `tests/` — pytest (`unit` = fast; `spark` = needs local JVM).

## Commands

```bash
# Python env + tests
.venv/Scripts/python.exe -m pytest -m "unit or spark" -q      # 40 tests
.venv/Scripts/python.exe -m ruff check . && black .

# Databricks (auth via KV PAT, no browser)
export DATABRICKS_HOST=https://adb-7405608693609813.13.azuredatabricks.net
export DATABRICKS_TOKEN="$(az keyvault secret show --vault-name ghan-dev-kv-a5k8k --name databricks-pat --query value -o tsv)"
databricks bundle validate -t dev && databricks bundle deploy -t dev
# Trigger medallion job (what ADF does):
databricks jobs run-now --json '{"job_id":304513597804481,"job_parameters":{"env":"dev","execution_date":"2024-01-15","landing_path":"abfss://landing@ghanalyticsdeva5k8k.dfs.core.windows.net/gharchive/year=2024/month=01/day=15/hour=00/","source_file":"2024-01-15-0.json.gz"}}'
```

## Conventions

- **Pure functions + thin notebooks**: transformation logic is I/O-free in `src/transformations` (unit-tested locally); notebooks only read/MERGE/write.
- **Idempotency everywhere**: bronze/silver MERGE on `event_id`; gold `replaceWhere` by `event_date`. Re-running any hour/day is a no-op.
- **Schema enforced by construction**: bronze reads text + `get_json_object` (no inference); `payload` kept as raw JSON string. Bad rows → `ops.quarantine`.
- **Config-driven**: table names via `cfg.table(layer, name)`; env via the `env` widget.
- **No secrets in code or chat** — Key Vault only, set via `az keyvault secret set` typed in a terminal.

## Gotchas (learned the hard way)

- **Serverless**: no `.cache()`/`.persist()`; `pyyaml` not preinstalled → add via job `environments` (`client: "2"`, `dependencies: [pyyaml==6.0.2]`). Classic DBR has both.
- **Windows local Spark**: set `PYSPARK_PYTHON=sys.executable` + `SPARK_LOCAL_IP=127.0.0.1` (in conftest) or workers fail to connect back. `winutils` warning is harmless for pure-transform tests.
- **Git Bash + databricks CLI**: prefix `/Workspace/...` paths with `MSYS_NO_PATHCONV=1` or they get mangled to `C:/Program Files/Git/...`.
- **Logging**: context is nested under one attr so reserved LogRecord keys (`name`, `module`) can be logged safely.
- `az role assignment` fails with `MissingSubscription` in the sandbox shell → do RBAC via Terraform.

## Status: Phases 0–3 done & validated on real data. Phase 4 (ADF) in progress.

Revisit-later: UC managed tables use GUID storage paths (by design) — switch to
external tables if browsable paths are wanted.
