"""Gold-layer aggregations.

Event-only tables take just ``silver.events``. The trend tables also take the
current ``silver.repos_scd2`` snapshot (repo_id → language / topics) to attach
metadata.

Pure functions — each takes DataFrames and returns an aggregated DataFrame.
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def _count_when(condition) -> F.Column:
    return F.sum(F.when(condition, 1).otherwise(0))


def event_type_summary_hourly(events: DataFrame) -> DataFrame:
    """Event volume by (date, hour, event_type)."""
    return (
        events.groupBy("event_date", "event_hour", "event_type")
        .agg(
            F.count("*").alias("event_count"),
            F.countDistinct("actor_id").alias("unique_actors"),
            F.countDistinct("repo_id").alias("unique_repos"),
        )
        .withColumn("gold_processed_at", F.current_timestamp())
    )


def hot_repos_hourly(events: DataFrame) -> DataFrame:
    """Per-repo hourly activity — the source for 'trending repos'."""
    is_type = lambda t: F.col("event_type") == t  # noqa: E731
    return (
        events.groupBy("event_date", "event_hour", "repo_id", "repo_name", "repo_owner")
        .agg(
            F.count("*").alias("event_count"),
            F.countDistinct("actor_id").alias("unique_actors"),
            _count_when(is_type("WatchEvent")).alias("stars"),
            _count_when(is_type("ForkEvent")).alias("forks"),
            _count_when(is_type("PushEvent")).alias("pushes"),
            _count_when(is_type("PullRequestEvent")).alias("pull_requests"),
            _count_when(is_type("IssuesEvent")).alias("issues"),
        )
        .withColumn("gold_processed_at", F.current_timestamp())
    )


def contributor_activity_daily(events: DataFrame) -> DataFrame:
    """Per-actor daily activity (bots retained but flagged)."""
    is_type = lambda t: F.col("event_type") == t  # noqa: E731
    opened = F.col("event_action") == "opened"
    return (
        events.groupBy("event_date", "actor_id", "actor_login", "is_bot")
        .agg(
            F.count("*").alias("total_events"),
            F.countDistinct("repo_id").alias("repos_touched"),
            _count_when(is_type("PushEvent")).alias("push_events"),
            _count_when(is_type("PullRequestEvent")).alias("pr_events"),
            _count_when(is_type("PullRequestEvent") & opened).alias("prs_opened"),
            _count_when(is_type("IssuesEvent")).alias("issue_events"),
            _count_when(is_type("IssuesEvent") & opened).alias("issues_opened"),
            _count_when(is_type("WatchEvent")).alias("stars_given"),
        )
        .withColumn("gold_processed_at", F.current_timestamp())
    )


def _current_repos(repos_scd2: DataFrame) -> DataFrame:
    """Current-version repo metadata (repo_id, primary_language, topics)."""
    return repos_scd2.filter(F.col("is_current")).select("repo_id", "primary_language", "topics")


def language_trends_daily(events: DataFrame, repos_scd2: DataFrame) -> DataFrame:
    """Daily activity by repo primary language (events joined to repo metadata)."""
    repos = _current_repos(repos_scd2)
    return (
        events.join(repos, "repo_id", "inner")
        .filter(F.col("primary_language").isNotNull())
        .groupBy("event_date", "primary_language")
        .agg(
            F.count("*").alias("event_count"),
            F.countDistinct("repo_id").alias("unique_repos"),
            F.countDistinct("actor_id").alias("unique_actors"),
            _count_when(F.col("event_type") == "WatchEvent").alias("stars"),
        )
        .withColumn("gold_processed_at", F.current_timestamp())
    )


def topic_trends_daily(events: DataFrame, repos_scd2: DataFrame) -> DataFrame:
    """Daily activity by repo topic (topics are comma-joined; exploded here)."""
    repos = _current_repos(repos_scd2).filter(
        (F.col("topics").isNotNull()) & (F.col("topics") != "")
    )
    exploded = repos.withColumn("topic", F.explode(F.split("topics", ","))).select(
        "repo_id", "topic"
    )
    return (
        events.join(exploded, "repo_id", "inner")
        .groupBy("event_date", "topic")
        .agg(
            F.count("*").alias("event_count"),
            F.countDistinct("repo_id").alias("unique_repos"),
            F.countDistinct("actor_id").alias("unique_actors"),
        )
        .withColumn("gold_processed_at", F.current_timestamp())
    )
