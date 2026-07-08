# Phased Delivery Plan

Each phase is tested before the next begins. Manual steps (portal clicks, token
generation, ADF Studio authorization) are called out explicitly.

| # | Phase | Status |
|---|---|---|
| 0 | Project bootstrap — repo scaffold, tooling, CI-ready | ✅ In progress |
| 1 | Azure infrastructure (Terraform): RG, ADLS Gen2, Event Hubs, Key Vault, ADF, **Databricks workspace**, RBAC | ⬜ |
| 2 | Databricks setup — Asset Bundle, KV-backed secret scope, cluster policies, Unity Catalog check | ⬜ |
| 3 | Databricks notebooks — bronze / silver / gold / DQ + unit tests | ⬜ |
| 4 | ADF linked services & datasets (JSON) + Studio authorization | ⬜ |
| 5 | ADF main hourly pipeline — Copy + notebook activities, end-to-end test | ⬜ |
| 6 | ADF backfill pipeline — ForEach + parallelism | ⬜ |
| 7 | Silver enhancements — repo metadata enrichment, SCD Type 2 | ⬜ |
| 8 | Gold completion — all aggregates, OPTIMIZE + Z-ORDER | ⬜ |
| 9 | Data quality framework — GX suites, `ops.dq_results`, ADF integration | ⬜ |
| 10 | Streaming — Event Hubs producer + Structured Streaming Workflow | ⬜ |
| 11 | ADF triggers — hourly / daily / 6-hourly | ⬜ |
| 12 | CI/CD — PR checks + deploy (dev auto, prod approval) | ⬜ |
| 13 | Dashboards — Databricks SQL operational + Power BI business | ⬜ |
| 14 | Documentation — diagrams, data dictionary, runbook, cost analysis | ⬜ |

## Key decisions locked

- **Region:** `centralindia`
- **Databricks tier:** Premium (Unity Catalog targeted)
- **ADF workflow:** Git-integrated Studio (syncs JSON to repo)
- **Databricks workspace:** provisioned by Terraform in Phase 1 (none pre-existed)
- **Subscription:** `d5f98fab-893f-45ce-9fdc-c3399ba9f46f` / tenant `7fe6f6b6-...`

## Deviations from original spec

- Spec assumed a Databricks workspace already existed and the CLI was
  authenticated to it. In reality the subscription had **no** Databricks
  workspace, so Phase 1 Terraform provisions one, and the Unity Catalog check
  moves to Phase 2 (can't auth a CLI to a workspace that doesn't exist).
