#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
remote_required=false
if [[ ${1:-} == "--remote-required" ]]; then
  remote_required=true
elif [[ $# -ne 0 ]]; then
  echo "usage: zhaoniu-backup [--remote-required]" >&2
  exit 2
fi

repo_dir=${ZHAONIU_REPO:-/opt/zhiniu/repo}
env_file=${ZHAONIU_ENV_FILE:-/etc/zhiniu/staging.env}
release_env=${ZHAONIU_RELEASE_ENV:-/opt/zhiniu/releases/current/release.env}
backup_env_file=${ZHAONIU_BACKUP_ENV_FILE:-/etc/zhiniu/backup.env}
backup_dir=${ZHAONIU_BACKUP_DIR:-/var/backups/zhiniu}
project_name=${ZHAONIU_PROJECT_NAME:-zhaoniu-staging}
compose_file=${repo_dir}/infrastructure/production/docker-compose.yml

[[ -f ${env_file} ]] || { echo "missing environment file" >&2; exit 1; }
[[ -f ${release_env} ]] || { echo "missing active release environment" >&2; exit 1; }
[[ -f ${backup_env_file} ]] || { echo "missing backup environment" >&2; exit 1; }

set -a
# shellcheck disable=SC1090
source "${backup_env_file}"
set +a

: "${BACKUP_AGE_RECIPIENT:?set BACKUP_AGE_RECIPIENT}"
if ${remote_required}; then
  : "${BACKUP_REMOTE:?set BACKUP_REMOTE for required off-host backup}"
fi

for command in age docker python3 sha256sum; do
  command -v "${command}" >/dev/null || { echo "missing command: ${command}" >&2; exit 1; }
done

mkdir -p "${backup_dir}"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
raw_file=${backup_dir}/zhaoniu-${stamp}.dump
encrypted_file=${raw_file}.age
manifest_file=${backup_dir}/zhaoniu-${stamp}.json
trap 'rm -f -- "${raw_file}"' EXIT

compose=(
  docker compose --project-name "${project_name}"
  --env-file "${env_file}" --env-file "${release_env}"
  -f "${compose_file}"
)

"${compose[@]}" exec -T postgres sh -c \
  'pg_dump --format=custom --no-owner --username="$POSTGRES_USER" "$POSTGRES_DB"' \
  >"${raw_file}"
"${compose[@]}" exec -T postgres pg_restore --list <"${raw_file}" >/dev/null

raw_sha=$(sha256sum "${raw_file}" | awk '{print $1}')
migration_head=$("${compose[@]}" exec -T postgres sh -c \
  'psql --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" -Atc "SELECT version_num FROM alembic_version"')
age --recipient "${BACKUP_AGE_RECIPIENT}" --output "${encrypted_file}" "${raw_file}"
encrypted_sha=$(sha256sum "${encrypted_file}" | awk '{print $1}')

RAW_SHA="${raw_sha}" ENCRYPTED_SHA="${encrypted_sha}" MIGRATION_HEAD="${migration_head}" \
ARTIFACT_NAME="$(basename "${encrypted_file}")" MANIFEST_FILE="${manifest_file}" \
python3 - <<'PY'
import json
import os
from datetime import UTC, datetime
from pathlib import Path

Path(os.environ["MANIFEST_FILE"]).write_text(
    json.dumps(
        {
            "created_at": datetime.now(UTC).isoformat(),
            "artifact": os.environ["ARTIFACT_NAME"],
            "format": "postgres-custom-age",
            "raw_sha256": os.environ["RAW_SHA"],
            "sha256": os.environ["ENCRYPTED_SHA"],
            "migration_head": os.environ["MIGRATION_HEAD"],
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
PY

rm -f -- "${raw_file}"
trap - EXIT

if [[ -n ${BACKUP_REMOTE:-} ]]; then
  : "${BACKUP_SSH_KEY:?set BACKUP_SSH_KEY}"
  : "${BACKUP_KNOWN_HOSTS:?set BACKUP_KNOWN_HOSTS}"
  [[ -f ${BACKUP_SSH_KEY} ]] || { echo "backup SSH key not found" >&2; exit 1; }
  [[ -f ${BACKUP_KNOWN_HOSTS} ]] || { echo "backup known_hosts not found" >&2; exit 1; }
  command -v rsync >/dev/null || { echo "missing command: rsync" >&2; exit 1; }
  rsync --archive --protect-args \
    -e "ssh -i ${BACKUP_SSH_KEY} -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=${BACKUP_KNOWN_HOSTS}" \
    -- "${encrypted_file}" "${manifest_file}" "${BACKUP_REMOTE%/}/"
elif ${remote_required}; then
  echo "remote backup is required" >&2
  exit 1
fi

find "${backup_dir}" -maxdepth 1 -type f \
  \( -name 'zhaoniu-*.dump.age' -o -name 'zhaoniu-*.json' \) -mtime +3 -delete
echo "backup=${encrypted_file} sha256=${encrypted_sha} migration=${migration_head}"
