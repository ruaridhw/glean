#!/usr/bin/env bash
# Point an AWS CLI profile at an IAM user (service principal) whose access key
# lives in 1Password. Run by `make aws-profile`; safe to re-run.
#
#   scripts/aws_op_profile.sh op://<vault>/<item> [profile] [ssh-host]   # profile defaults to glean
#
# Copies scripts/aws_op_credentials.sh next to the AWS config (so the profile
# keeps working after this checkout or worktree is removed) and sets the
# profile's credential_process to it. The CLI then runs `op inject` whenever it
# needs the key; with the 1Password desktop app's CLI integration on, that is
# a Touch ID prompt at most every ten minutes. Give an ssh-host (e.g. the Mac
# with the 1Password app) and `op` runs there over SSH instead, so this
# machine needs no 1Password sign-in of its own.
#
# 1Password references cannot contain parentheses; if the item's title has
# any, use its ID (op://<vault>/<item-id>).
set -euo pipefail

item="${1:?1Password item reference, e.g. op://<vault>/<item> (set OP_AWS_ITEM in .env.local)}"
profile="${2:-glean}"
ssh_host="${3:-}"
region="${AWS_REGION:-${AWS_DEFAULT_REGION:-eu-west-2}}"

config="${AWS_CONFIG_FILE:-$HOME/.aws/config}"
helper="$(dirname "$config")/op-credentials.sh"

mkdir -p "$(dirname "$config")"
install -m 700 "$(dirname "${BASH_SOURCE[0]}")/aws_op_credentials.sh" "$helper"

aws configure set --profile "$profile" credential_process "\"$helper\" \"$item\"${ssh_host:+ \"$ssh_host\"}"
aws configure set --profile "$profile" region "$region"

# Static keys in ~/.aws/credentials win over credential_process, so a profile
# that still has them would silently keep using the copy on disk.
if [[ -n "$(aws configure get --profile "$profile" aws_access_key_id 2>/dev/null || true)" ]]; then
  echo "warning: profile '$profile' still has aws_access_key_id/aws_secret_access_key in" >&2
  echo "  ${AWS_SHARED_CREDENTIALS_FILE:-$HOME/.aws/credentials}; delete that section so 1Password is used." >&2
fi

echo "profile '$profile' now reads its key from $item${ssh_host:+ via $ssh_host}"
