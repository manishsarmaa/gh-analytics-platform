"""Shared pytest fixtures.

The ``spark`` fixture builds a local Delta-enabled SparkSession, reused across
the whole test session. Tests that need it must be marked ``@pytest.mark.spark``
and will be skipped automatically if PySpark/Java are unavailable.
"""

from __future__ import annotations

import pytest

try:
    from pyspark.sql import SparkSession

    _PYSPARK_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYSPARK_AVAILABLE = False


@pytest.fixture(scope="session")
def spark():  # type: ignore[no-untyped-def]
    if not _PYSPARK_AVAILABLE:
        pytest.skip("pyspark not installed")

    builder = (
        SparkSession.builder.appName("gh-analytics-tests")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.ui.enabled", "false")
    )

    try:
        from delta import configure_spark_with_delta_pip

        session = configure_spark_with_delta_pip(builder).getOrCreate()
    except Exception:  # pragma: no cover - delta jars unavailable locally
        session = builder.getOrCreate()

    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()
