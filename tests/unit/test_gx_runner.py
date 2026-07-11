"""Unit tests for the Great Expectations runner (pandas backend)."""

from __future__ import annotations

import pandas as pd
import pytest

from dq.gx_runner import run_suite
from dq.runner import has_critical_failure

pytestmark = pytest.mark.unit


def test_run_suite_detects_failures():
    pdf = pd.DataFrame(
        {"name": ["a", None, "c"], "event_type": ["PushEvent", "Xevent", "WatchEvent"]}
    )
    suite = [
        {
            "type": "expect_column_values_to_not_be_null",
            "kwargs": {"column": "name"},
            "severity": "warning",
        },
        {
            "type": "expect_column_values_to_be_in_set",
            "kwargs": {"column": "event_type", "value_set": ["PushEvent", "WatchEvent"]},
            "severity": "warning",
        },
    ]
    by_name = {r.check_name: r for r in run_suite(pdf, suite)}
    assert by_name["gx:expect_column_values_to_not_be_null:name"].passed is False
    assert by_name["gx:expect_column_values_to_be_in_set:event_type"].passed is False


def test_run_suite_all_pass():
    pdf = pd.DataFrame({"name": ["a", "b"]})
    suite = [
        {
            "type": "expect_column_values_to_not_be_null",
            "kwargs": {"column": "name"},
            "severity": "warning",
        },
    ]
    results = run_suite(pdf, suite)
    assert results[0].passed is True
    assert results[0].check_type == "great_expectations_sample"
    # warning-severity findings never trip the critical gate
    assert not has_critical_failure(results)
