output "bucket_name" {
  description = "Name of the provisioned R2 backup bucket."
  value       = cloudflare_r2_bucket.backup.name
}

output "bucket_domain" {
  description = "Managed public domain for the R2 bucket (requires public access to be enabled on the bucket)."
  # cloudflare_r2_bucket exposes domains.managed once the bucket exists.
  # Falls back to a constructed value if the attribute is not yet populated.
  value = try(
    cloudflare_r2_bucket.backup.domains[0].managed,
    "${cloudflare_r2_bucket.backup.name}.${var.account_id}.r2.cloudflarestorage.com"
  )
}
