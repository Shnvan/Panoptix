output "bucket_name" {
  description = "Name of the provisioned R2 backup bucket."
  value       = cloudflare_r2_bucket.backup.name
}

output "bucket_domain" {
  description = "S3-compatible endpoint for the R2 bucket."
  value       = "${var.account_id}.r2.cloudflarestorage.com"
}
