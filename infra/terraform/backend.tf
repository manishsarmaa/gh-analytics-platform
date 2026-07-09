# Remote state in Azure Storage. The backend is intentionally empty here and
# filled at init time from a generated backend config:
#
#   terraform init -backend-config=backend.hcl
#
# Run infra/terraform/bootstrap/bootstrap-state.ps1 once first — it creates the
# state storage account and writes backend.hcl. See infra/terraform/README.md.
terraform {
  backend "azurerm" {}
}
