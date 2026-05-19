# Terraform State Security

## Why state is sensitive

Terraform state (`terraform.tfstate`) contains plaintext representations of every managed
resource, including database connection strings, API keys, service account credentials, and
other secrets. Anyone with read access to the state file has effective access to all
credentials it references. Do not treat state as a non-secret artifact.

## Required backend — do NOT use local state

Local `terraform.tfstate` files must not be used for staging or production. Acceptable
backends:

| Backend | Notes |
|---------|-------|
| **Terraform Cloud** (free tier) | Preferred. Provides encryption, locking, audit log, and RBAC out of the box. |
| **AWS S3 + DynamoDB locking** | S3 bucket with SSE-S3 or SSE-KMS encryption; DynamoDB table for state locking. |

Never commit `terraform.tfstate` or `terraform.tfstate.backup` to version control.
Both are listed in `.gitignore` — verify this is enforced before any `terraform apply`.

## Encryption at rest

State must be encrypted at rest at the storage layer:

- Terraform Cloud: encrypted by default.
- S3: enable `aws:kms` or `AES256` server-side encryption on the bucket; block all public access.

## Access control

Only the designated CI/CD service account (System Owner role) should have write access to
the state backend. Human operators may have read access for incident investigation, but
write access must be restricted to the automation principal. Apply least-privilege IAM
policies; do not share state bucket credentials broadly.

## State locking

All applies must acquire a state lock before executing. This prevents concurrent `terraform
apply` runs from corrupting state. Terraform Cloud and the S3+DynamoDB backend both support
locking natively — do not disable locking (`-lock=false`) outside of a documented break-glass
recovery.

## Audit log

Every state read and write should be attributable to a principal and timestamp.
Terraform Cloud provides an Organization Audit Trail natively. For S3, enable S3 server
access logging and CloudTrail data events on the state bucket.

## If state is accidentally committed to git

Treat it as a confirmed secret leak:

1. Immediately rotate **all** credentials referenced in the state (DB passwords, API keys,
   service tokens, etc.).
2. Notify the System Owner and log the incident.
3. Remove the file from git history using `git filter-repo --path terraform.tfstate --invert-paths`.
   A simple `git rm` is not sufficient — the file remains in history.
4. Force-push the cleaned history to all remotes and invalidate cached clones.
5. Confirm `.gitignore` entries for `terraform.tfstate` and `terraform.tfstate.backup` are
   present and committed before any further Terraform work resumes.
