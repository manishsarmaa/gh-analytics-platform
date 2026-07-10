# Dashboards (Phase 13)

Two dashboards over the gold layer:

- **Databricks SQL** — operational (platform health + activity), code-first queries
- **Power BI** — business (trends, leaderboards), DirectQuery to Databricks

Both read `gh_analytics_dev.gold.*` (+ `ops.dq_results`, `silver.repos_scd2`) via
the **Serverless Starter Warehouse**. Queries are validated on real data (see
`databricks_sql/operational_queries.sql`).

## A. Databricks SQL operational dashboard

1. In the workspace: **SQL → Queries → Create query**. Paste each query from
   [`databricks_sql/operational_queries.sql`](databricks_sql/operational_queries.sql),
   run on the **Serverless Starter Warehouse**, and **Save** (name it after the
   `-- N.` comment).
2. **SQL → Dashboards → Create dashboard**. Add one visualization per query:
   | Query | Viz |
   |---|---|
   | 1 DQ pass rate | Counter / bar (pass_pct by layer) |
   | 2 Event-type distribution | Pie/bar |
   | 3 Trending repos | Table (bar on contributors) |
   | 4 Language trends | Horizontal bar |
   | 5 Top topics | Bar |
   | 6 Top contributors | Table |
   | 7 Bot vs human | Donut |
   | 8 Hourly pattern | Line (event_hour) |
   | 9 SCD2 versions | Counter |
3. Set the dashboard to the serverless warehouse; optionally schedule a refresh.
4. Export the dashboard JSON (⋯ → Export) into `databricks_sql/` to keep it in Git.

## B. Power BI business dashboard (DirectQuery)

Get the warehouse connection details: **SQL → SQL Warehouses → Serverless Starter
Warehouse → Connection details** (Server hostname + **HTTP path**).

1. **Power BI Desktop → Get Data → Azure Databricks**.
2. Enter **Server hostname** and **HTTP Path**; Data Connectivity mode: **DirectQuery**.
3. Auth: **Azure Active Directory** (or Personal Access Token = the `databricks-pat`).
4. Navigator → expand `gh_analytics_dev` → `gold` → select:
   `hot_repos_hourly`, `language_trends_daily`, `topic_trends_daily`,
   `event_type_summary_hourly`, `contributor_activity_daily`.
5. Suggested visuals:
   - **Trending repos** — bar chart (repo_name by contributors), top 20
   - **Language trends** — treemap/bar (events by primary_language)
   - **Activity over time** — line (events by event_hour)
   - **Event mix** — donut (event_type share)
   - **Contributor leaderboard** — table (actor_login by prs_opened, `is_bot = false`)
   - KPI cards: total events, distinct repos, distinct contributors
6. **Publish** to the Power BI Service; save the `.pbix` under `powerbi/`.

> DirectQuery keeps visuals live against Delta (no import/refresh lag). The
> serverless warehouse auto-starts on query and auto-stops when idle.
