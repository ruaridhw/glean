#!/usr/bin/env bash
set -euo pipefail

REGION="eu-west-2"
STACK_NAME="glean-bootstrap"

# Where DynamoDB budget alerts go. Never hard-code it: this repo is public.
# Usage: ALERT_EMAIL=<your address> infra/bootstrap.sh   (or: infra/bootstrap.sh <your address>)
ALERT_EMAIL="${1:-${ALERT_EMAIL:-}}"
if [ -z "$ALERT_EMAIL" ]; then
  echo "error: set ALERT_EMAIL (or pass the address as the first argument); the DynamoDB budget alert needs it" >&2
  exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "==> Creating SAM artefact S3 buckets..."
aws s3 mb "s3://glean-sam-artefacts-prod-${ACCOUNT_ID}" --region "$REGION" 2>/dev/null || echo "  glean-sam-artefacts-prod-${ACCOUNT_ID} already exists"
aws s3 mb "s3://glean-sam-artefacts-dev-${ACCOUNT_ID}" --region "$REGION" 2>/dev/null || echo "  glean-sam-artefacts-dev-${ACCOUNT_ID} already exists"

echo "==> Deploying OIDC provider and IAM roles..."
# Note: if the OIDC provider already exists in your account, this will fail.
# In that case, import the existing resource or remove the GitHubOidcProvider resource
# from bootstrap.yaml and update the GleanDeployRole* resources to reference the ARN directly.
sam deploy \
  --template-file infra/bootstrap.yaml \
  --stack-name "$STACK_NAME" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION" \
  --parameter-overrides "AlertEmail=$ALERT_EMAIL" \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset

echo ""
echo "==> Stack outputs (paste these into GitHub):"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[*].{Key:OutputKey,Value:OutputValue}' \
  --output table

echo ""
echo "Next steps:"
echo "  1. In GitHub → Settings → Environments → Create 'prod' environment"
echo "     Add secret: AWS_ROLE_ARN = <GleanDeployRoleProdArn from above>"
echo "     Add required reviewer protection"
echo "  2. In GitHub → Settings → Secrets → Repository secrets"
echo "     Add: AWS_ROLE_ARN_DEV = <GleanDeployRoleDevArn from above>"
