-- =============================================================================
-- Serving views for the dashboards (Databricks SQL + Power BI).
-- Created in gh_analytics_dev.gold as vw_*. Dashboards/BI query these directly;
-- ordering/limits are applied by the tile. Re-runnable (CREATE OR REPLACE).
-- =============================================================================

-- Platform health: DQ pass rate by layer (custom + Great Expectations)
CREATE OR REPLACE VIEW gh_analytics_dev.gold.vw_dq_health AS
SELECT layer,
       count(*)                                                            AS checks,
       sum(CASE WHEN passed THEN 1 ELSE 0 END)                             AS passed,
       round(100.0 * sum(CASE WHEN passed THEN 1 ELSE 0 END) / count(*), 1) AS pass_pct
FROM gh_analytics_dev.ops.dq_results
GROUP BY layer;

-- Event-type distribution
CREATE OR REPLACE VIEW gh_analytics_dev.gold.vw_event_type_distribution AS
SELECT event_type,
       sum(event_count)   AS events,
       sum(unique_actors) AS actors
FROM gh_analytics_dev.gold.event_type_summary_hourly
GROUP BY event_type;

-- Trending repositories (rank by contributors in the tile)
CREATE OR REPLACE VIEW gh_analytics_dev.gold.vw_trending_repos AS
SELECT repo_name,
       sum(unique_actors) AS contributors,
       sum(event_count)   AS events,
       sum(stars)         AS stars,
       sum(forks)         AS forks
FROM gh_analytics_dev.gold.hot_repos_hourly
GROUP BY repo_name;

-- Language trends (enriched repos)
CREATE OR REPLACE VIEW gh_analytics_dev.gold.vw_language_trends AS
SELECT primary_language,
       sum(event_count)  AS events,
       sum(unique_repos) AS repos,
       sum(stars)        AS stars
FROM gh_analytics_dev.gold.language_trends_daily
WHERE primary_language IS NOT NULL
GROUP BY primary_language;

-- Topic trends
CREATE OR REPLACE VIEW gh_analytics_dev.gold.vw_topic_trends AS
SELECT topic,
       sum(event_count)  AS events,
       sum(unique_repos) AS repos
FROM gh_analytics_dev.gold.topic_trends_daily
GROUP BY topic;

-- Top human contributors by REAL contribution (spam-resistant: PRs/issues opened)
CREATE OR REPLACE VIEW gh_analytics_dev.gold.vw_top_contributors AS
SELECT actor_login,
       sum(prs_opened)    AS prs_opened,
       sum(issues_opened) AS issues_opened,
       sum(repos_touched) AS repos,
       sum(total_events)  AS events
FROM gh_analytics_dev.gold.contributor_activity_daily
WHERE NOT is_bot
GROUP BY actor_login
HAVING sum(prs_opened) + sum(issues_opened) > 0;

-- Bot vs human activity split
CREATE OR REPLACE VIEW gh_analytics_dev.gold.vw_bot_vs_human AS
SELECT CASE WHEN is_bot THEN 'bot' ELSE 'human' END AS actor_kind,
       sum(total_events)           AS events,
       count(DISTINCT actor_login) AS actors
FROM gh_analytics_dev.gold.contributor_activity_daily
GROUP BY is_bot;

-- Hourly activity pattern (UTC)
CREATE OR REPLACE VIEW gh_analytics_dev.gold.vw_hourly_activity AS
SELECT event_hour,
       sum(event_count) AS events
FROM gh_analytics_dev.gold.event_type_summary_hourly
GROUP BY event_hour;

-- Batch vs streaming contribution to silver
CREATE OR REPLACE VIEW gh_analytics_dev.gold.vw_batch_vs_stream AS
SELECT source,
       count(*) AS events
FROM gh_analytics_dev.silver.events
GROUP BY source;

-- SCD2 repo dimension: current vs historical versions
CREATE OR REPLACE VIEW gh_analytics_dev.gold.vw_repo_versions AS
SELECT is_current,
       count(*) AS rows
FROM gh_analytics_dev.silver.repos_scd2
GROUP BY is_current;
