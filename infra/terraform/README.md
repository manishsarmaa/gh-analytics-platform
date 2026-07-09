# Terraform — Azure Infrastructure

Provisions all Azure resources for the platform: resource group, ADLS Gen2,
Event Hubs, Key Vault, Azure Databricks (Premium) + access connector, Azure Data
Factory (managed identity), and RBAC role assignments.

## Modules

| Module | Creates |
|---|---|
| `storage` | ADLS Gen2 account, 6 containers, landing lifecycle policy |
| `keyvault` | Key Vault (RBAC auth) |
| `eventhub` | Event Hubs namespace + `gh-events` hub + auth rule |
| `databricks` | Premium workspace + Unity Catalog access connector |
| `adf` | Data Factory with system-assigned managed identity |
| `rbac` | Role assignments (ADF/Databricks/user → Storage & Key Vault) |

## Prerequisites

- `az login` done, correct subscription selected.
- Resource providers registered: `Microsoft.Databricks`, `Microsoft.EventHub`,
  `Microsoft.KeyVault`, `Microsoft.Storage`, `Microsoft.DataFactory`,
  `Microsoft.ManagedIdentity`, `Microsoft.Authorization`.
- Terraform >= 1.5.

## Run order

```powershell
# 1. One-time: create the remote-state backend (writes backend.hcl)
cd infra/terraform/bootstrap
./bootstrap-state.ps1 -Env dev

# 2. Init against the remote backend
cd ..
terraform init -backend-config=backend.hcl

# 3. Plan (review every resource before applying)
terraform plan -var-file=environments/dev.tfvars -out=tfplan

# 4. Apply
terraform apply tfplan

# 5. Read the outputs — copy them into configs/dev.yaml
terraform output config_updates_needed
```

## After apply

1. Update `configs/dev.yaml` with the values from `terraform output
   config_updates_needed` (real storage account name, KV name, ADF name,
   Databricks workspace URL, resource group).
2. Manually add secrets to Key Vault (you have Secrets Officer via RBAC):
   ```powershell
   az keyvault secret set --vault-name <kv-name> --name github-pat     --value <YOUR_GITHUB_PAT>
   az keyvault secret set --vault-name <kv-name> --name databricks-pat  --value <YOUR_DATABRICKS_PAT>
   ```
   (The `eventhub-connection-string` secret is created by Terraform.)

## Cost notes (idle)

| Resource | Idle cost |
|---|---|
| Resource group, RBAC | Free |
| ADLS Gen2 | ~₹0 empty; pennies/GB stored |
| Event Hubs **Basic** | ~₹0.90/hr namespace — the main idle cost. Destroy when not in use. |
| Key Vault | Free tier; ~₹0.03 / 10k operations |
| **Databricks workspace** | **Free** — you pay only when clusters run |
| **ADF** | Free at rest; ~₹0.85 per 1,000 activity runs + pipeline orchestration |

> The cost driver is **cluster runtime**, not these resources. Destroy Event
> Hubs (or the whole stack) with `terraform destroy` between work sessions to
> preserve trial credit.

## State backend

Remote state lives in `stght<subhash>` / `tfstate` container, key
`ghanalytics.<env>.tfstate`. `backend.hcl` is generated (git-ignored) and not
committed. Regenerate it any time with `bootstrap-state.ps1`.
