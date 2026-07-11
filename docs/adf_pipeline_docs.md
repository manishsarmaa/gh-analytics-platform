# ADF Pipelines

All pipelines are code-first JSON under [`adf/`](../adf/) (Studio Git-integrated,
root `/adf`). They orchestrate **serverless Databricks jobs** via the Jobs API
(Web Activity, **managed-identity** auth — resource `2ff814a6-…`). No secrets.

## Pattern: trigger + poll + fail
Each job-triggering pipeline: **Web Activity** `run-now` → **SetVariable** run_id →
**Until** (Wait 30s → **Web** `runs/get` → update lifecycle/result) until terminal →
**If** result≠SUCCESS → **Fail** (surfaces to ADF monitoring/alerts). The result
read is null-safe: `@if(contains(...output.state,'result_state'), …, '')`.

## Pipelines

| Pipeline | Parameters | Does |
|---|---|---|
| `pl_hourly_ingestion` | `run_time`="" , `hour_offset`=-2, `env`=dev | Derive y/m/d/h from run time → **Copy** GH Archive hour → landing → trigger `gh_medallion_batch` → poll. |
| `pl_backfill_historical` | `start_date`, `end_date`, `start_hour`=0, `end_hour`=2 | `range()` → **ForEach** (batchCount 3, parallel) → **Execute** `pl_hourly_ingestion` per hour. |
| `pl_repo_metadata_refresh` | `env`, `batch_size`=100 | Trigger `gh_repo_metadata_refresh` (GitHub API → `silver.repos_scd2`). |
| `pl_daily_optimization` | `env`, `vacuum_retention_hours`=168 | Trigger `gh_daily_maintenance` (OPTIMIZE+ZORDER+VACUUM). |

## Linked services / datasets
- `HTTP_GHArchive_LS` (anonymous), `ADLS_Landing_LS` (ADF MI).
- `DS_GHArchive_Source` (Binary, `file_name`), `DS_Landing_Sink` (Binary,
  `folder_path`+`file_name`). Files kept `.gz` (byte copy).

## Triggers (defined, `runtimeState: Stopped` — enable in Studio)
| Trigger | Schedule | Pipeline |
|---|---|---|
| `tr_hourly` | hourly at :15 | `pl_hourly_ingestion` |
| `tr_daily_optimization` | 02:00 UTC daily | `pl_daily_optimization` |
| `tr_repo_refresh` | every 6h | `pl_repo_metadata_refresh` |

## Job ids (dev)
medallion `304513597804481` · repo-metadata `544994714197226` ·
maintenance `683550268106263` · streaming `565008359980272`.
