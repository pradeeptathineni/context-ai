# AWS infrastructure

Use the project's existing Terraform/AWS stack. Inspect identity, backend/state ownership, versions, environment and destination before planning. Keep site source separate from infrastructure. Read-only source inspection does not prove current cloud state.

Use format/validation and a saved plan with bounded identity/state authority. Prefer an isolated backend-disabled validation directory when the project permits it; never initialize against retained state by accident. Plans can contain private values: store locally and do not publish them.

For static sites inspect private S3/CloudFront access, TLS/ACM region, Route53 ownership, paths/errors, cache behavior and deployment/invalidation permissions. Define rollback before release. No loadout command runs apply/destroy, uploads a site, changes DNS or grants credentials.

Source-supported interfaces: [Terraform validate](https://developer.hashicorp.com/terraform/cli/commands/validate), [AWS CloudFront S3 origins](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html). Reviewed 2026-10-05. Project-specific deployment authority remains explicit.
