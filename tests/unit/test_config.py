"""Unit tests for the environment-config loader."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from utils.config import Config, load_config


@pytest.fixture
def dev_config() -> Config:
    return load_config("dev")


@pytest.mark.unit
def test_dev_config_loads_and_matches_env(dev_config: Config) -> None:
    assert dev_config.env == "dev"
    assert dev_config.raw["azure"]["location"] == "centralindia"


@pytest.mark.unit
def test_abfss_path_construction(dev_config: Config) -> None:
    path = dev_config.abfss("bronze", "gh_events_batch")
    account = dev_config.storage_account
    assert path == f"abfss://bronze@{account}.dfs.core.windows.net/gh_events_batch"


@pytest.mark.unit
def test_abfss_strips_leading_slash(dev_config: Config) -> None:
    assert dev_config.abfss("landing", "/gharchive/").endswith("/gharchive/")
    assert "net//" not in dev_config.abfss("landing", "/gharchive")


@pytest.mark.unit
def test_table_name_unity_three_level(tmp_path: Path) -> None:
    cfg = _write_and_load(tmp_path, metastore="unity", catalog="gh_analytics_dev")
    assert cfg.table("bronze", "gh_events_batch") == "gh_analytics_dev.bronze.gh_events_batch"


@pytest.mark.unit
def test_table_name_hive_two_level(tmp_path: Path) -> None:
    cfg = _write_and_load(tmp_path, metastore="hive", catalog="ignored")
    assert cfg.table("bronze", "gh_events_batch") == "bronze.gh_events_batch"


@pytest.mark.unit
def test_missing_env_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent", config_dir=str(tmp_path))


@pytest.mark.unit
def test_get_returns_default_for_missing_key(dev_config: Config) -> None:
    assert dev_config.get("does", "not", "exist", default="fallback") == "fallback"


def _write_and_load(tmp_path: Path, *, metastore: str, catalog: str) -> Config:
    """Write a minimal valid config to a temp dir and load it."""
    (tmp_path / "t.yaml").write_text(
        textwrap.dedent(
            f"""
            env: t
            storage:
              account_name: acct
              containers: {{bronze: bronze, landing: landing}}
            catalog:
              metastore_type: {metastore}
              catalog_name: {catalog}
              schemas: {{bronze: bronze}}
            """
        ).strip(),
        encoding="utf-8",
    )
    return load_config("t", config_dir=str(tmp_path))
