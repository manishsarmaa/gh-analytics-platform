-- =============================================================================
-- Databricks SQL — operational dashboard queries (catalog: gh_analytics_dev)
-- Each query backs one dashboard tile. Run on the serverless SQL warehouse.
-- =============================================================================

-- 1. Platform health: DQ pass rate by layer (last runs)
SELECT layer,
       count(*)                                         AS checks,
       sum(CASE WHEN passed THEN 1 ELSE 0 END)          AS passed,
       round(100.0 * sum(CASE WHEN passed THEN 1 ELSE 0 END) / count(*), 1) AS pass_pct
FROM gh_analytics_dev.ops.dq_results
GROUP BY layer
ORDER BY layer;

-- 2. Event-type distribution (share of activity)
SELECT event_type,
       sum(event_count)   AS events,
       sum(unique_actors) AS actors
FROM gh_analytics_dev.gold.event_type_summary_hourly
GROUP BY event_type
ORDER BY events DESC;

-- 3. Trending repositories (by distinct actors, then activity)
SELECT repo_name,
       sum(unique_actors) AS contributors,
       sum(event_count)   AS events,
       sum(stars)         AS stars,
       sum(forks)         AS forks
FROM gh_analytics_dev.gold.hot_repos_hourly
GROUP BY repo_name
ORDER BY contributors DESC, events DESC
LIMIT 20;

-- 4. Language trends (enriched repos)
SELECT primary_language,
       sum(event_count)  AS events,
       sum(unique_repos) AS repos,
       sum(stars)        AS stars
FROM gh_analytics_dev.gold.language_trends_daily
GROUP BY primary_language
ORDER BY events DESC
LIMIT 15;

-- 5. Top topics
SELECT topic,
       sum(event_count)  AS events,
       sum(unique_repos) AS repos
FROM gh_analytics_dev.gold.topic_trends_daily
GROUP BY topic
ORDER BY events DESC
LIMIT 20;

-- 6. Top human contributors by REAL contribution (PRs/issues opened).
--    Ranking by raw events surfaces push-spam accounts; PR/issue activity is a
--    far better signal (spam floods pushes but never opens PRs).
SELECT actor_login,
       sum(prs_opened)    AS prs_opened,
       sum(issues_opened) AS issues_opened,
       sum(repos_touched) AS repos,
       sum(total_events)  AS events
FROM gh_analytics_dev.gold.contributor_activity_daily
WHERE NOT is_bot
GROUP BY actor_login
HAVING sum(prs_opened) + sum(issues_opened) > 0
ORDER BY prs_opened DESC, issues_opened DESC, repos DESC
LIMIT 20;

-- 7. Bot vs human activity split
SELECT CASE WHEN is_bot THEN 'bot' ELSE 'human' END AS actor_kind,
       sum(total_events)          AS events,
       count(DISTINCT actor_login) AS actors
FROM gh_analytics_dev.gold.contributor_activity_daily
GROUP BY is_bot;

-- 8. Hourly activity pattern (UTC)
SELECT event_hour,
       sum(event_count) AS events
FROM gh_analytics_dev.gold.event_type_summary_hourly
GROUP BY event_hour
ORDER BY event_hour;

-- 9. SCD2 repo dimension: current vs historical versions
SELECT is_current,
       count(*) AS rows
FROM gh_analytics_dev.silver.repos_scd2
GROUP BY is_current;
