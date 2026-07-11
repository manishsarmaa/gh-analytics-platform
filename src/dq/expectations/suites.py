"""Great Expectations suites per layer (declarative), run on a pandas sample.

Each expectation is ``{type, kwargs, severity}``. ``gx_runner.run_suite`` executes
them against a pandas sample and maps results to ``CheckResult`` so they share the
``ops.dq_results`` sink with the custom runner.

Scope: column-value expectations that are meaningful on a sample (null presence,
accepted values, types). Full-table guarantees (row count, uniqueness) live in
the Spark-native custom runner (``dq.runner``), which is the critical gate — so
GX findings here are ``warning`` severity.
"""

from __future__ import annotations

KNOWN_EVENT_TYPES = [
    "PushEvent",
    "PullRequestEvent",
    "IssuesEvent",
    "IssueCommentEvent",
    "WatchEvent",
    "ForkEvent",
    "CreateEvent",
    "DeleteEvent",
    "ReleaseEvent",
    "PullRequestReviewEvent",
    "PullRequestReviewCommentEvent",
    "CommitCommentEvent",
    "GollumEvent",
    "MemberEvent",
    "PublicEvent",
]


def _not_null(col):
    return {
        "type": "expect_column_values_to_not_be_null",
        "kwargs": {"column": col},
        "severity": "warning",
    }


def _in_set(col, values):
    return {
        "type": "expect_column_values_to_be_in_set",
        "kwargs": {"column": col, "value_set": values},
        "severity": "warning",
    }


BRONZE = [_not_null("event_id"), _not_null("event_type"), _not_null("repo_id")]

SILVER = [
    _not_null("event_id"),
    _not_null("repo_id"),
    _in_set("event_type", KNOWN_EVENT_TYPES),
    _in_set("is_bot", [True, False]),
]

GOLD = [_not_null("event_date")]

SUITES = {"bronze": BRONZE, "silver": SILVER, "gold": GOLD}


def suite_for(layer: str) -> list[dict]:
    return SUITES.get(layer, GOLD)
