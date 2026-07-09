<#
.SYNOPSIS
    One-time bootstrap of the Terraform remote-state backend.

.DESCRIPTION
    Creates a resource group + storage account + "tfstate" container to hold
    Terraform state, then writes infra/terraform/backend.hcl for `terraform init`.

    The storage account name is derived deterministically from the subscription
    ID, so re-running this script is idempotent (it reuses the same account).

.EXAMPLE
    ./bootstrap-state.ps1 -Env dev
    cd ..
    terraform init -backend-config=backend.hcl
#>
param(
    [string]$Env = "dev",
    [string]$Location = "centralindia"
)

$ErrorActionPreference = "Stop"

$sub = az account show --query id -o tsv
if (-not $sub) { throw "Not logged in. Run 'az login' first." }

$rg        = "rg-ghanalytics-tfstate"
$subHex    = ($sub -replace '-', '').Substring(0, 8)
$sa        = "stght$subHex"          # e.g. stghtd5f98fab — global-unique, <=24 chars
$container = "tfstate"

Write-Host "Subscription : $sub"
Write-Host "State RG     : $rg"
Write-Host "State SA     : $sa"
Write-Host ""

Write-Host "Creating resource group..."
az group create --name $rg --location $Location --output none

Write-Host "Creating state storage account (versioned, shared-key)..."
az storage account create `
    --name $sa `
    --resource-group $rg `
    --location $Location `
    --sku Standard_LRS `
    --kind StorageV2 `
    --min-tls-version TLS1_2 `
    --allow-blob-public-access false `
    --output none

# Enable blob versioning so state history is recoverable.
az storage account blob-service-properties update `
    --account-name $sa `
    --resource-group $rg `
    --enable-versioning true `
    --output none

Write-Host "Creating '$container' container..."
$key = az storage account keys list --resource-group $rg --account-name $sa --query "[0].value" -o tsv
az storage container create --name $container --account-name $sa --account-key $key --output none

# Write backend config (no BOM — Terraform's HCL parser dislikes it).
$backendPath = Join-Path $PSScriptRoot "..\backend.hcl"
$backendPath = [System.IO.Path]::GetFullPath($backendPath)
$content = @"
resource_group_name  = "$rg"
storage_account_name = "$sa"
container_name       = "$container"
key                  = "ghanalytics.$Env.tfstate"
"@
[System.IO.File]::WriteAllText($backendPath, $content)

Write-Host ""
Write-Host "Done. Wrote backend config to: $backendPath"
Write-Host "Next:"
Write-Host "  cd $([System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')))"
Write-Host "  terraform init -backend-config=backend.hcl"
Write-Host "  terraform plan  -var-file=environments/$Env.tfvars -out=tfplan"
Write-Host "  terraform apply tfplan"
