#!/usr/bin/env bash
# AWS CLI `credential_process` that reads an IAM user's access key from
# 1Password each time the CLI needs it, so the key never sits on disk in
# ~/.aws/credentials. `make aws-profile` (scripts/aws_op_profile.sh) installs
# a copy and points a profile at it.
#
#   aws_op_credentials.sh op://<vault>/<item> [ssh-host]
#
# With an ssh-host, `op` runs on that machine instead (a Mac with the
# 1Password app), so a headless box needs no 1Password session of its own:
# each fetch unlocks through the app there, with a Touch ID prompt when it is
# locked. The secret comes back over the SSH connection and is never written
# to either machine's disk or command line.
#
# The item needs fields labelled "access key id" and "secret access key", the
# labels 1Password's own AWS shell plugin uses.
set -euo pipefail

item="${1:?1Password item reference, e.g. op://<vault>/<item>}"
ssh_host="${2:-}"

# One `op inject` fills both fields, so a fetch is one unlock and one round trip.
template="$(printf '{"Version": 1, "AccessKeyId": "{{ %s/access key id }}", "SecretAccessKey": "{{ %s/secret access key }}"}' "$item" "$item")"

if [[ -n "$ssh_host" ]]; then
  # A non-interactive SSH shell on macOS does not have Homebrew on its PATH.
  printf '%s\n' "$template" \
    | ssh -o BatchMode=yes "$ssh_host" 'PATH=/opt/homebrew/bin:/usr/local/bin:$PATH op inject'
else
  printf '%s\n' "$template" | op inject
fi
