"""Environment-config loader.

Single source of truth for env-specific values. Notebooks call
``load_config(env)`` (env comes from the ADF-passed ``env`` widget) and read
storage paths, table names, and resource identifiers from the returned object.

Design:
- YAML holds non-secret config (paths, names, toggles).
- Secrets are NEVER in YAML — resolve them at runtime via ``dbutils.secrets``
  (Databricks) or Azure Key Vault SDK (local/containers).
- ``abfss`` paths are derived, not stored, so a storage-account rename is a
  one-line change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"


@dataclass(frozen=True)
class Config:
    """Parsed, validated view over an environment YAML file."""

    env: str
    raw: dict[str, Any] = field(repr=False)

    # ---- storage ---------------------------------------------------------
    @property
    def storage_account(self) -> str:
        return self.raw["storage"]["account_name"]

    def container(self, name: str) -> str:
        return self.raw["storage"]["containers"][name]

    def abfss(self, container: str, sub_path: str = "") -> str:
        """Build an abfss:// URI for a container (+ optional sub-path)."""
        base = f"abfss://{self.container(container)}@{self.storage_account}.dfs.core.windows.net"
        return f"{base}/{sub_path.lstrip('/')}" if sub_path else base

    # ---- catalog / tables ------------------------------------------------
    @property
    def metastore_type(self) -> str:
        return self.raw["catalog"]["metastore_type"]

    @property
    def catalog_name(self) -> str:
        return self.raw["catalog"]["catalog_name"]

    def schema(self, layer: str) -> str:
        return self.raw["catalog"]["schemas"][layer]

    def table(self, layer: str, table: str) -> str:
        """Fully-qualified table name, UC (3-level) or Hive (2-level)."""
        schema = self.schema(layer)
        if self.metastore_type == "unity":
            return f"{self.catalog_name}.{schema}.{table}"
        return f"{schema}.{table}"

    # ---- convenience accessors ------------------------------------------
    def get(self, *keys: str, default: Any = None) -> Any:
        node: Any = self.raw
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node


@lru_cache(maxsize=8)
def load_config(env: str | None = None, config_dir: str | None = None) -> Config:
    """Load and cache the config for ``env`` (defaults to $ENV or 'dev')."""
    env = (env or os.environ.get("ENV") or "dev").lower()
    directory = Path(config_dir) if config_dir else _CONFIG_DIR
    path = directory / f"{env}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No config for env '{env}': expected {path}")
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if raw.get("env") != env:
        raise ValueError(f"Config env mismatch: file says '{raw.get('env')}', requested '{env}'")
    return Config(env=env, raw=raw)
