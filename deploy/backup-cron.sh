#!/bin/sh
# Install with host cron + flock; env file path is the first argument. Failure is a nonzero exit.
set -eu
: "${1:?usage: backup-cron.sh /absolute/private/staging.env}"
docker compose --env-file "$1" -f "$(dirname "$0")/compose.yml" run --rm --no-deps backup
