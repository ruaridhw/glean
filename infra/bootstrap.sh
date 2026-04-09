#!/usr/bin/env bash
set -euo pipefail

REGION="eu-west-2"
STACK_NAME="glean-bootstrap"

echo "==> Creating SAM artifact S3 buckets..."
aws s3 mb s3://glean-sam-artifacts-prod --region "$REGION" 2>/dev/null || echo "  glean-sam-artifacts-prod already exists"
aws s3 mb s3://glean-sam-artifacts-dev --region "$REGION" 2>/dev/null || echo "  glean-sam-artifacts-dev already exists"

echo "==> Deploying OIDC provider and IAM roles..."
# Note: if the OIDC provider already exists in your account, this will fail.
# In that case, import the existing resource or remove the GitHubOidcProvider resource
# from bootstrap.yaml and update the GleanDeployRole* resources to reference the ARN directly.
sam deploy \
  --template-file infra/bootstrap.yaml \
  --stack-name "$STACK_NAME" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION" \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset

echo "==> Storing runtime secrets in Secrets Manager..."
echo "  Enter your Anthropic API key (sk-ant-...):"
read -rs ANTHROPIC_KEY
aws secretsmanager create-secret \
  --name "glean/prod/anthropic-api-key" \
  --secret-string "$ANTHROPIC_KEY" \
  --region "$REGION" 2>/dev/null || \
aws secretsmanager put-secret-value \
  --secret-id "glean/prod/anthropic-api-key" \
  --secret-string "$ANTHROPIC_KEY" \
  --region "$REGION"

echo "  Enter your Recipe API key (rapi_...):"
read -rs RECIPE_KEY
aws secretsmanager create-secret \
  --name "glean/prod/recipe-api-key" \
  --secret-string "$RECIPE_KEY" \
  --region "$REGION" 2>/dev/null || \
aws secretsmanager put-secret-value \
  --secret-id "glean/prod/recipe-api-key" \
  --secret-string "$RECIPE_KEY" \
  --region "$REGION"

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
echo "     Add: EXPO_TOKEN = <your EAS access token from expo.dev/accounts>"
