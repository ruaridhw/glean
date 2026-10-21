#!/usr/bin/env bash
# AWS CLI `credential_process` that reads an IAM user's access key from
# 1Password each time the CLI needs it, so the key never sits on disk in
# ~/.aws/credentials. `make aws-profile` (scripts/aws_op_profile.sh) installs
# a copy and points a profile at it.
#
#   aws_op_credentials.sh op://<vault>/<item>
#
# The item needs fields labelled "access key id" and "secret access key", the
# labels 1Password's own AWS shell plugin uses.
set -euo pipefail

item="${1:?1Password item reference, e.g. op://<vault>/<item>}"
key_id="$(op read "$item/access key id")"
secret="$(op read "$item/secret access key")"
printf '{"Version": 1, "AccessKeyId": "%s", "SecretAccessKey": "%s"}\n' "$key_id" "$secret"
