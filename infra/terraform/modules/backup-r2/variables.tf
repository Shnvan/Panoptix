variable "account_id" {
  type        = string
  description = "Cloudflare account ID that owns the R2 bucket."
}

variable "bucket_name" {
  type        = string
  default     = "panoptix-backups"
  description = "Name of the R2 bucket. Must be globally unique within the account."
}

variable "environment" {
  type        = string
  default     = "staging"
  description = "Deployment environment (staging or production). Used for tagging/naming conventions."

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be either 'staging' or 'production'."
  }
}
