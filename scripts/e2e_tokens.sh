#!/usr/bin/env bash
# Sign the dedicated Cognito test user in with USER_PASSWORD_AUTH and print
# its tokens, for the e2e entrypoint's bypass session (lib/main_e2e.dart).
#
#   scripts/e2e_tokens.sh --dart-defines   # one line of --dart-define=E2E_*_TOKEN=... for flutter
#   scripts/e2e_tokens.sh --exports        # export E2E_*_TOKEN=... lines for `eval`
#
# Reads E2E_USERNAME, E2E_PASSWORD and COGNITO_CLIENT_ID from the environment,
# falling back to the repo-root .env.local (gitignored). The dev pool's client
# allows USER_PASSWORD_AUTH with no client secret, so the AWS CLI needs no
# credentials for this call; AWS_REGION defaults to eu-west-2.
#
# Tokens are short-lived (the access token lasts an hour) and belong to a
# test user with no server-side data, but they are still bearer tokens:
# never paste them into a commit, an issue or a log.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$repo_root/.env.local" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$repo_root/.env.local"
  set +a
fi

: "${E2E_USERNAME:?set E2E_USERNAME in .env.local or the environment}"
: "${E2E_PASSWORD:?set E2E_PASSWORD in .env.local or the environment}"
: "${COGNITO_CLIENT_ID:?set COGNITO_CLIENT_ID (the dev pool app client) in .env.local or the environment}"
region="${AWS_REGION:-${AWS_DEFAULT_REGION:-eu-west-2}}"

result="$(aws cognito-idp initiate-auth \
  --region "$region" \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id "$COGNITO_CLIENT_ID" \
  --auth-parameters "USERNAME=$E2E_USERNAME,PASSWORD=$E2E_PASSWORD" \
  --query 'AuthenticationResult.[AccessToken,IdToken,RefreshToken]' \
  --output text)"
read -r access id refresh <<<"$result"
if [[ -z "$access" || "$access" == "None" ]]; then
  echo "e2e_tokens: Cognito returned no tokens (a challenge such as NEW_PASSWORD_REQUIRED? see scripts/e2e_user.sh)" >&2
  exit 1
fi

case "${1:---exports}" in
  --dart-defines)
    printf -- '--dart-define=E2E_ACCESS_TOKEN=%s --dart-define=E2E_ID_TOKEN=%s --dart-define=E2E_REFRESH_TOKEN=%s\n' \
      "$access" "$id" "$refresh"
    ;;
  --exports)
    printf 'export E2E_ACCESS_TOKEN=%q\nexport E2E_ID_TOKEN=%q\nexport E2E_REFRESH_TOKEN=%q\n' \
      "$access" "$id" "$refresh"
    ;;
  *)
    echo "usage: $0 [--dart-defines|--exports]" >&2
    exit 2
    ;;
esac
