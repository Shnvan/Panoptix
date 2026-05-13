# Panoptix backup-r2 module
# Provisions a Cloudflare R2 bucket for append-only CCTV backup storage.
# IMPORTANT: Deletion of backup objects must be done manually — no lifecycle
# expiry or bucket deletion is managed here to prevent accidental data loss.

terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }
}

resource "cloudflare_r2_bucket" "backup" {
  account_id = var.account_id
  name       = var.bucket_name
  location   = "WNAM" # West North America — co-located with Railway (US region)
}
