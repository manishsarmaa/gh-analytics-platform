"""Shared pytest fixtures.

The ``spark`` fixture builds a plain local SparkSession, reused across the whole
test session. Tests that need it must be marked ``@pytest.mark.spark`` and are
skipped automatically if PySpark/Java are unavailable.

Note: no Delta extensions here — unit tests exercise *pure DataFrame transforms*
only. Delta MERGE/write behavior is validated on Databricks (integration), not
locally, so we avoid the Maven jar download that Delta config would trigger.
"""

from __future__ import annotations

import os
import sys

import pytest

# Windows: make the Spark worker use THIS interpreter (else "Python worker failed
# to connect back") and force loopback so the worker can reach the driver.
os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")

try:
    from pyspark.sql import SparkSession

    _PYSPARK_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYSPARK_AVAILABLE = False


@pytest.fixture(scope="session")
def spark():  # type: ignore[no-untyped-def]
    if not _PYSPARK_AVAILABLE:
        pytest.skip("pyspark not installed")

    session = (
        SparkSession.builder.appName("gh-analytics-tests")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()
