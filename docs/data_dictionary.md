# Data Dictionary

Catalog `gh_analytics_dev` (Unity Catalog), schemas `bronze / silver / gold / ops`.
Managed Delta tables in ADLS (bronze/silver/gold in their own containers).

## bronze

### `bronze.gh_events_batch` (+ `gh_events_stream`)
Schema-enforced raw events. Partitioned by `event_date`. MERGE key `event_id`.

| Column | Type | Notes |
|---|---|---|
| event_id | string | GH event id (PK) |
| event_type | string | PushEvent, PullRequestEvent, … |
| actor_id / actor_login | long / string | actor |
| repo_id / repo_name | long / string | `owner/name` |
| payload | string | raw event payload (JSON string) |
| event_timestamp | timestamp | UTC |
| event_date | date | partition |
| ingestion_timestamp | timestamp | load time |
| source_file | string | lineage (filename or `eventhub`) |

## silver

### `silver.events`
Cleaned, deduplicated, parsed events — **unified batch + streaming**.

| Column | Type | Notes |
|---|---|---|
| event_id | string | PK (dedup) |
| event_type, event_action | string | action = payload.action |
| actor_id, actor_login, is_bot | … | `is_bot` = login ends `[bot]` |
| repo_id, repo_name, repo_owner | … | owner split out |
| ref, ref_type, push_size, pr_or_issue_number, pr_merged | … | promoted payload fields |
| payload | string | full payload retained |
| event_timestamp, event_date, event_hour | … | |
| source | string | `batch` or `stream` |
| silver_processed_at | timestamp | |

### `silver.repos_scd2` (SCD Type 2)
Repo dimension with history. Current row = `is_current AND valid_to IS NULL`.

| Column | Type | Notes |
|---|---|---|
| repo_id | long | business key |
| repo_name, primary_language, description | string | |
| stargazers_count, forks_count, open_issues_count, size_kb | int | |
| topics | string | comma-joined |
| is_fork | boolean | |
| record_hash | string | change detection (tracked cols) |
| valid_from / valid_to | timestamp | validity window (`valid_to` null = open) |
| is_current | boolean | |

## gold (partitioned by `event_date`)

| Table | Grain | Key measures |
|---|---|---|
| `event_type_summary_hourly` | date, hour, event_type | event_count, unique_actors, unique_repos |
| `hot_repos_hourly` | date, hour, repo | event_count, unique_actors, stars, forks, pushes, PRs, issues |
| `contributor_activity_daily` | date, actor | total_events, repos_touched, push/pr/issue events, prs_opened, issues_opened |
| `language_trends_daily` | date, primary_language | event_count, unique_repos, unique_actors, stars |
| `topic_trends_daily` | date, topic | event_count, unique_repos, unique_actors |

## ops

| Table | Purpose |
|---|---|
| `ops.dq_results` | one row per check: check_name, check_type (`row_count`/`not_null`/`unique`/`accepted_values`/`great_expectations_sample`), severity, passed, observed, expected, layer, table, run_id, execution_date, checked_at |
| `ops.quarantine` | dead-letter: event_id, source_file, ingestion_timestamp, dq_reason, raw_record |
