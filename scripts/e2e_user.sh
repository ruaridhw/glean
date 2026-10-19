#!/usr/bin/env bash
# Create (or reset the password of) the dedicated Cognito test user in the
# *dev* user pool. Run once by a human with AWS credentials for the account;
# scripts/e2e_tokens.sh then signs this user in without any credentials.
#
#   scripts/e2e_user.sh <user-pool-id> <email-username> <password>
#
# The user is created with a permanent password and a verified email so no
# confirmation or NEW_PASSWORD_REQUIRED challenge gets in the way. Put the
# username and password in the repo-root .env.local as E2E_USERNAME and
# E2E_PASSWORD (and as GitHub Actions secrets if CI should use them).
set -euo pipefail

pool="${1:?user pool id (the dev pool; see the glean-api-dev stack UserPoolId output)}"
username="${2:?username (the pool uses email addresses as usernames), e.g. e2e-test-user@example.invalid}"
password="${3:?password meeting the pool password policy}"
region="${AWS_REGION:-${AWS_DEFAULT_REGION:-eu-west-2}}"

if ! aws cognito-idp admin-get-user --region "$region" --user-pool-id "$pool" --username "$username" >/dev/null 2>&1; then
  aws cognito-idp admin-create-user \
    --region "$region" \
    --user-pool-id "$pool" \
    --username "$username" \
    --user-attributes Name=email,Value="$username" Name=email_verified,Value=true \
    --message-action SUPPRESS >/dev/null
  echo "created $username in $pool"
fi
aws cognito-idp admin-set-user-password \
  --region "$region" \
  --user-pool-id "$pool" \
  --username "$username" \
  --password "$password" \
  --permanent
echo "password set (permanent) for $username"
