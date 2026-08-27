#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

if [[ ${EUID} -ne 0 ]]; then
  echo "zhaoniu-deploy must run as root" >&2
  exit 1
fi
if [[ $# -ne 3 ]]; then
  echo "usage: zhaoniu-deploy COMMIT_SHA API_IMAGE@sha256:DIGEST WEB_IMAGE@sha256:DIGEST" >&2
  exit 2
fi

commit_sha=$1
api_image=$2
web_image=$3

[[ ${commit_sha} =~ ^[0-9a-f]{40}$ ]] || { echo "invalid commit sha" >&2; exit 2; }
[[ ${api_image} =~ ^ghcr\.io/wepuu/zhiniu-api@sha256:[0-9a-f]{64}$ ]] || {
  echo "invalid API image" >&2
  exit 2
}
[[ ${web_image} =~ ^ghcr\.io/wepuu/zhiniu-web@sha256:[0-9a-f]{64}$ ]] || {
  echo "invalid Web image" >&2
  exit 2
}

root_dir=${ZHAONIU_ROOT:-/opt/zhiniu}
repo_dir=${ZHAONIU_REPO:-${root_dir}/repo}
releases_dir=${ZHAONIU_RELEASES:-${root_dir}/releases}
env_file=${ZHAONIU_ENV_FILE:-/etc/zhiniu/staging.env}
backup_script=${ZHAONIU_BACKUP_SCRIPT:-/usr/local/sbin/zhaoniu-backup}
backup_env_file=${ZHAONIU_BACKUP_ENV_FILE:-/etc/zhiniu/backup.env}
docker_root=${ZHAONIU_DOCKER_ROOT:-/var/lib/docker}
min_free_kb=${ZHAONIU_MIN_FREE_KB:-15728640}
min_available_kb=${ZHAONIU_MIN_AVAILABLE_KB:-524288}
project_name=${ZHAONIU_PROJECT_NAME:-zhaoniu-staging}
lock_file=${ZHAONIU_LOCK_FILE:-/run/lock/zhaoniu-deploy.lock}

for command in curl docker flock git python3; do
  command -v "${command}" >/dev/null || { echo "missing command: ${command}" >&2; exit 1; }
done
[[ -f ${env_file} ]] || { echo "missing environment file: ${env_file}" >&2; exit 1; }
[[ -d ${repo_dir}/.git ]] || { echo "missing repository: ${repo_dir}" >&2; exit 1; }
[[ -d ${docker_root} ]] || { echo "missing Docker root: ${docker_root}" >&2; exit 1; }

trusted_host=$(sed -n 's/^[[:space:]]*TRUSTED_HOSTS=//p' "${env_file}" | head -n 1 | cut -d, -f1 | tr -d '[:space:]')
[[ ${trusted_host} =~ ^([A-Za-z0-9-]+\.)*[A-Za-z0-9-]+$ ]] || {
  echo "invalid or missing first TRUSTED_HOSTS entry" >&2
  exit 1
}

mkdir -p "${releases_dir}" "$(dirname "${lock_file}")"
exec 9>"${lock_file}"
flock -n 9 || { echo "another deployment is running" >&2; exit 1; }

free_kb=$(df -Pk "${docker_root}" | awk 'NR == 2 { print $4 }')
available_kb=$(awk '/MemAvailable:/ { print $2 }' /proc/meminfo)
[[ ${free_kb} -ge ${min_free_kb} ]] || { echo "deployment blocked: less than 15GB free" >&2; exit 1; }
[[ ${available_kb} -ge ${min_available_kb} ]] || {
  echo "deployment blocked: less than 512MB available memory" >&2
  exit 1
}

git -C "${repo_dir}" fetch --depth=1 origin main
main_sha=$(git -C "${repo_dir}" rev-parse FETCH_HEAD)
[[ ${main_sha} == "${commit_sha}" ]] || {
  echo "deployment blocked: requested commit is no longer main" >&2
  exit 1
}
git -C "${repo_dir}" checkout --detach "${commit_sha}"
checked_out=$(git -C "${repo_dir}" rev-parse HEAD)
[[ ${checked_out} == "${commit_sha}" ]] || { echo "checked out commit mismatch" >&2; exit 1; }

compose_file=${repo_dir}/infrastructure/production/docker-compose.yml
[[ -f ${compose_file} ]] || { echo "missing production compose file" >&2; exit 1; }

release_dir=${releases_dir}/${commit_sha}
mkdir -p "${release_dir}"
release_env=${release_dir}/release.env
printf 'API_IMAGE=%s\nWEB_IMAGE=%s\n' "${api_image}" "${web_image}" >"${release_env}"

compose() {
  docker compose \
    --project-name "${project_name}" \
    --env-file "${env_file}" \
    --env-file "${release_env}" \
    -f "${compose_file}" \
    "$@"
}

previous_dir=""
if [[ -L ${releases_dir}/current ]]; then
  previous_dir=$(readlink -f "${releases_dir}/current")
fi

postgres_id=$(compose ps -q postgres 2>/dev/null || true)
if [[ -n ${postgres_id} ]] && [[ $(docker inspect -f '{{.State.Running}}' "${postgres_id}") == true ]]; then
  [[ -x ${backup_script} ]] || { echo "missing backup script: ${backup_script}" >&2; exit 1; }
  ZHAONIU_REPO="${repo_dir}" \
  ZHAONIU_ENV_FILE="${env_file}" \
  ZHAONIU_RELEASE_ENV="${release_env}" \
  ZHAONIU_BACKUP_ENV_FILE="${backup_env_file}" \
    "${backup_script}" --remote-required
fi

docker pull "${api_image}"
docker pull "${web_image}"
for image in "${api_image}" "${web_image}"; do
  image_revision=$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "${image}")
  image_architecture=$(docker image inspect --format '{{.Architecture}}' "${image}")
  [[ ${image_revision} == "${commit_sha}" ]] || { echo "image revision does not match commit" >&2; exit 1; }
  [[ ${image_architecture} == "amd64" ]] || { echo "image architecture is not amd64" >&2; exit 1; }
done
compose up -d postgres redis
compose run --rm migrate
compose up -d --remove-orphans api worker beat web

wait_for_health() {
  local attempt
  for attempt in $(seq 1 40); do
    if curl --fail --silent --show-error --max-time 3 \
      --header "Host: ${trusted_host}" http://127.0.0.1:8000/readyz >/dev/null \
      && curl --fail --silent --show-error --max-time 3 http://127.0.0.1:3000/ >/dev/null \
      && service_is_stable worker \
      && service_is_stable beat; then
      return 0
    fi
    sleep 3
  done
  return 1
}

service_is_stable() {
  local container_id
  container_id=$(compose ps -q "$1" 2>/dev/null)
  [[ -n ${container_id} ]] \
    && [[ $(docker inspect --format '{{.State.Running}}' "${container_id}") == true ]] \
    && [[ $(docker inspect --format '{{.RestartCount}}' "${container_id}") -eq 0 ]]
}

if ! wait_for_health; then
  echo "new release failed health checks" >&2
  if [[ -n ${previous_dir} && -f ${previous_dir}/release.env ]]; then
    release_env=${previous_dir}/release.env
    compose up -d --remove-orphans api worker beat web
    wait_for_health || echo "previous release also failed health checks" >&2
  fi
  exit 1
fi

migration_head=$(compose exec -T postgres sh -c \
  'psql --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" -Atc "SELECT version_num FROM alembic_version"')

if [[ -n ${previous_dir} && ${previous_dir} != "${release_dir}" ]]; then
  ln -sfn "${previous_dir}" "${releases_dir}/previous"
fi
ln -sfn "${release_dir}" "${releases_dir}/current"

COMMIT_SHA="${commit_sha}" API_IMAGE="${api_image}" WEB_IMAGE="${web_image}" \
MIGRATION_HEAD="${migration_head}" RELEASE_FILE="${release_dir}/current-release.json" \
python3 - <<'PY'
import json
import os
from datetime import UTC, datetime
from pathlib import Path

Path(os.environ["RELEASE_FILE"]).write_text(
    json.dumps(
        {
            "commit_sha": os.environ["COMMIT_SHA"],
            "api_image": os.environ["API_IMAGE"],
            "web_image": os.environ["WEB_IMAGE"],
            "migration_head": os.environ["MIGRATION_HEAD"],
            "deployed_at": datetime.now(UTC).isoformat(),
            "environment": "staging",
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
PY

mapfile -t release_paths < <(
  find "${releases_dir}" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' \
    | sort -nr | cut -d' ' -f2-
)
for ((index = 3; index < ${#release_paths[@]}; index++)); do
  old_dir=${release_paths[$index]}
  old_api=$(sed -n 's/^API_IMAGE=//p' "${old_dir}/release.env" 2>/dev/null || true)
  old_web=$(sed -n 's/^WEB_IMAGE=//p' "${old_dir}/release.env" 2>/dev/null || true)
  rm -rf -- "${old_dir}"
  [[ -z ${old_api} ]] || docker image rm "${old_api}" >/dev/null 2>&1 || true
  [[ -z ${old_web} ]] || docker image rm "${old_web}" >/dev/null 2>&1 || true
done

# Refresh root-owned operational assets only after the release is healthy. The running shell keeps
# its open file descriptor; the new copy applies to the next deployment.
install -m 0755 "${repo_dir}/infrastructure/production/deploy.sh" /usr/local/sbin/zhaoniu-deploy
install -m 0755 "${repo_dir}/infrastructure/production/backup.sh" /usr/local/sbin/zhaoniu-backup
install -m 0755 "${repo_dir}/infrastructure/production/restore-drill.sh" /usr/local/sbin/zhaoniu-restore-drill

echo "deployed ${commit_sha} at migration ${migration_head}"
