#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
if [[ $# -ne 2 ]]; then
  echo "usage: zhaoniu-restore-drill ENCRYPTED_BACKUP zhaoniu_restore_NAME" >&2
  exit 2
fi

artifact=$1
target_database=$2
[[ ${target_database} =~ ^zhaoniu_restore_[a-z0-9_]+$ ]] || {
  echo "restore database must start with zhaoniu_restore_" >&2
  exit 2
}

repo_dir=${ZHAONIU_REPO:-/opt/zhiniu/repo}
env_file=${ZHAONIU_ENV_FILE:-/etc/zhiniu/staging.env}
release_env=${ZHAONIU_RELEASE_ENV:-/opt/zhiniu/releases/current/release.env}
backup_env_file=${ZHAONIU_BACKUP_ENV_FILE:-/etc/zhiniu/backup.env}
project_name=${ZHAONIU_PROJECT_NAME:-zhaoniu-staging}
compose_file=${repo_dir}/infrastructure/production/docker-compose.yml

[[ -f ${artifact} ]] || { echo "backup not found" >&2; exit 1; }
manifest=${artifact%.dump.age}.json
[[ -f ${manifest} ]] || { echo "backup manifest not found" >&2; exit 1; }
[[ -f ${backup_env_file} ]] || { echo "backup environment not found" >&2; exit 1; }
set -a
# shellcheck disable=SC1090
source "${backup_env_file}"
set +a
: "${AGE_IDENTITY_FILE:?set AGE_IDENTITY_FILE}"

raw_file=$(mktemp --suffix=.dump)
trap 'rm -f -- "${raw_file}"' EXIT
actual_encrypted_sha=$(sha256sum "${artifact}" | awk '{print $1}')
expected_encrypted_sha=$(MANIFEST="${manifest}" python3 - <<'PY'
import json
import os
from pathlib import Path

print(json.loads(Path(os.environ["MANIFEST"]).read_text(encoding="utf-8"))["sha256"])
PY
)
[[ ${actual_encrypted_sha} == "${expected_encrypted_sha}" ]] || {
  echo "encrypted backup checksum mismatch" >&2
  exit 1
}
age --decrypt --identity "${AGE_IDENTITY_FILE}" --output "${raw_file}" "${artifact}"
actual_raw_sha=$(sha256sum "${raw_file}" | awk '{print $1}')
expected_raw_sha=$(MANIFEST="${manifest}" python3 - <<'PY'
import json
import os
from pathlib import Path

print(json.loads(Path(os.environ["MANIFEST"]).read_text(encoding="utf-8"))["raw_sha256"])
PY
)
[[ ${actual_raw_sha} == "${expected_raw_sha}" ]] || {
  echo "decrypted backup checksum mismatch" >&2
  exit 1
}

compose=(
  docker compose --project-name "${project_name}"
  --env-file "${env_file}" --env-file "${release_env}"
  -f "${compose_file}"
)
"${compose[@]}" exec -T postgres pg_restore --list <"${raw_file}" >/dev/null
"${compose[@]}" exec -T postgres sh -c \
  "dropdb --if-exists --username=\"\$POSTGRES_USER\" \"${target_database}\" && createdb --username=\"\$POSTGRES_USER\" \"${target_database}\""
"${compose[@]}" exec -T postgres sh -c \
  "pg_restore --no-owner --username=\"\$POSTGRES_USER\" --dbname=\"${target_database}\"" \
  <"${raw_file}"
restored_head=$("${compose[@]}" exec -T postgres sh -c \
  "psql --username=\"\$POSTGRES_USER\" --dbname=\"${target_database}\" -Atc 'SELECT version_num FROM alembic_version'")
key_counts=$("${compose[@]}" exec -T postgres sh -c \
  "psql --username=\"\$POSTGRES_USER\" --dbname=\"${target_database}\" -Atc \"SELECT 'users=' || count(*) FROM users UNION ALL SELECT 'stocks=' || count(*) FROM stocks UNION ALL SELECT 'research_snapshots=' || count(*) FROM research_snapshots\"")
printf 'target_database=%s migration_head=%s\n%s\n' "${target_database}" "${restored_head}" "${key_counts}"
