"""Run Great Expectations suites via the Pandas backend.

Why Pandas, not Spark: GX 0.18's Spark backend persists the DataFrame
internally, which Databricks **serverless** rejects
(``[NOT_SUPPORTED_WITH_SERVERLESS]``). We instead validate a bounded pandas
**sample** collected from the Spark table. The custom Spark runner
(``dq.runner``) remains the authoritative *full-table* gate; GX adds declarative,
richer expectation coverage (+ data-docs potential) on the sample.

Results map to the shared ``CheckResult`` type, so GX findings land in
``ops.dq_results`` beside the custom checks and share the critical-failure gate.
"""

from __future__ import annotations

from typing import Any

from dq.runner import CheckResult


def run_suite(pandas_df: Any, expectations: list[dict]) -> list[CheckResult]:
    """Execute GX expectations on a pandas DataFrame; one CheckResult each."""
    from great_expectations.dataset import PandasDataset

    dataset = PandasDataset(pandas_df)
    results: list[CheckResult] = []
    for exp in expectations:
        etype = exp["type"]
        kwargs = exp.get("kwargs", {})
        col = kwargs.get("column")
        outcome = getattr(dataset, etype)(**kwargs)
        res = outcome.result or {}
        observed = (
            f"unexpected={res.get('unexpected_count')}"
            if "unexpected_count" in res
            else str(res.get("observed_value", "ok"))
        )
        results.append(
            CheckResult(
                check_name="gx:" + etype + (f":{col}" if col else ""),
                check_type="great_expectations_sample",
                severity=exp.get("severity", "warning"),
                passed=bool(outcome.success),
                observed=observed,
                expected=etype,
            )
        )
    return results
