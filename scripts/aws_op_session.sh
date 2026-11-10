#!/usr/bin/env bash
# Mint a temporary STS session token for an AWS CLI profile and keep it in tmpfs
# (owner-only), so scripts and agents keep working after 1Password locks or the
# user walks away. Run by `make aws-profile` after scripts/aws_op_profile.sh,
# while the Touch ID prompt can still be answered; re-run to refresh.
#
#   scripts/aws_op_session.sh [profile]      # profile defaults to glean
#
# Writes $XDG_RUNTIME_DIR/aws-<profile>-session.env (mode 600), which is sourced
# with `unset AWS_PROFILE; . <file>`. The long-lived key never reaches disk, and
# a failed mint leaves the previous file untouched.
set -euo pipefail

profile="${1:-glean}"
hours="${AWS_SESSION_HOURS:-12}"
dir="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
file="$dir/aws-$profile-session.env"

mkdir -p "$dir"
umask 077
tmp="$(mktemp "$dir/.aws-session.XXXXXX")"
trap 'rm -f "$tmp"' EXIT

# Mint from the profile's own key, ignoring any session already exported.
reply="$(env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN \
  aws sts get-session-token --profile "$profile" \
  --duration-seconds $((hours * 3600)) --output json)"

printf '%s' "$reply" | python3 -I -c '
import json, sys
c = json.load(sys.stdin)["Credentials"]
print("# expires " + c["Expiration"])
print("export AWS_ACCESS_KEY_ID=" + c["AccessKeyId"])
print("export AWS_SECRET_ACCESS_KEY=" + c["SecretAccessKey"])
print("export AWS_SESSION_TOKEN=" + c["SessionToken"])
' >"$tmp"
region="$(aws configure get region --profile "$profile" 2>/dev/null || true)"
printf 'export AWS_DEFAULT_REGION=%s\n' "${region:-eu-west-2}" >>"$tmp"

mv "$tmp" "$file"
trap - EXIT

echo "session token ($(sed -n 's/^# expires /expires /p' "$file")) cached in $file"
echo "  use it with: unset AWS_PROFILE; . $file"
