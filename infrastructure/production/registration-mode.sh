#!/usr/bin/env bash
set -Eeuo pipefail

action=${1:-status}
env_file=${ZHAONIU_ENV_FILE:-/etc/zhiniu/staging.env}
release_env=${ZHAONIU_RELEASE_ENV:-/opt/zhiniu/releases/current/release.env}
compose_file=${ZHAONIU_COMPOSE_FILE:-/opt/zhiniu/repo/infrastructure/production/docker-compose.yml}
project_name=${ZHAONIU_PROJECT_NAME:-zhaoniu-staging}
lock_file=/run/lock/zhaoniu-registration-mode.lock

if [[ ${EUID} -ne 0 ]]; then
  echo "run as root on the application host" >&2
  exit 1
fi

case ${action} in
  status | open | close) ;;
  *)
    echo "usage: $0 {status|open|close}" >&2
    exit 2
    ;;
esac

if [[ ${ZHAONIU_REGISTRATION_LOCKED:-0} != 1 ]]; then
  exec flock -n "${lock_file}" env ZHAONIU_REGISTRATION_LOCKED=1 "$0" "$@"
fi

for path in "${env_file}" "${release_env}" "${compose_file}"; do
  [[ -f ${path} ]] || { echo "required file missing: ${path}" >&2; exit 1; }
done

current_mode=$(
  awk -F= '
    $1 == "REGISTRATION_MODE" { count += 1; value = $2 }
    END {
      if (count != 1) exit 2
      print value
    }
  ' "${env_file}"
) || { echo "expected exactly one REGISTRATION_MODE entry" >&2; exit 1; }

[[ ${current_mode} == closed || ${current_mode} == invite_only ]] || {
  echo "unsupported current registration mode: ${current_mode}" >&2
  exit 1
}

if [[ ${action} == status ]]; then
  echo "registration_mode=${current_mode}"
  exit 0
fi

target_mode=closed
[[ ${action} == open ]] && target_mode=invite_only

if [[ ${current_mode} == "${target_mode}" ]]; then
  echo "registration_mode=${current_mode}"
  echo "registration_mode_changed=no"
  exit 0
fi

backup_stamp=$(date -u '+%Y%m%dT%H%M%SZ')
env_backup="${env_file}.before-registration-${action}-${backup_stamp}"
install -m 0600 -o root -g root "${env_file}" "${env_backup}"
changed=no

rollback() {
  status=$?
  trap - ERR
  if [[ ${changed} == yes ]]; then
    echo "registration_mode_rollback=yes" >&2
    install -m 0600 -o root -g root "${env_backup}" "${env_file}"
    docker compose \
      --project-name "${project_name}" \
      --env-file "${env_file}" \
      --env-file "${release_env}" \
      -f "${compose_file}" \
      up -d --no-deps --force-recreate api worker || true
  fi
  exit "${status}"
}
trap rollback ERR

python3 - "${env_file}" "${target_mode}" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
target = sys.argv[2]
lines = path.read_text(encoding="utf-8").splitlines()
matches = [index for index, line in enumerate(lines) if line.startswith("REGISTRATION_MODE=")]
if len(matches) != 1:
    raise SystemExit(f"expected exactly one REGISTRATION_MODE entry, found {len(matches)}")
index = matches[0]
old = lines[index].split("=", 1)[1]
if old not in {"closed", "invite_only"}:
    raise SystemExit(f"unsupported current registration mode: {old}")
lines[index] = f"REGISTRATION_MODE={target}"
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
changed=yes

compose=(
  docker compose
  --project-name "${project_name}"
  --env-file "${env_file}"
  --env-file "${release_env}"
  -f "${compose_file}"
)
"${compose[@]}" config --quiet
"${compose[@]}" up -d --no-deps --force-recreate api worker

healthy=no
for attempt in $(seq 1 30); do
  api_health=$(
    docker inspect \
      --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
      "${project_name}-api-1"
  )
  if [[ ${api_health} == healthy ]]; then
    healthy=yes
    break
  fi
  sleep 2
done
[[ ${healthy} == yes ]] || { echo "API did not become healthy" >&2; exit 1; }

effective_mode=$(
  docker exec "${project_name}-api-1" python -c \
    'from zhaoniu_api.config import Settings; print(Settings().registration_mode)'
)
[[ ${effective_mode} == "${target_mode}" ]] || {
  echo "effective registration mode mismatch" >&2
  exit 1
}

docker exec "${project_name}-worker-1" \
  celery -A zhaoniu_worker.celery_app:celery_app inspect ping --timeout 10 >/dev/null

trap - ERR
changed=no
echo "registration_mode=${effective_mode}"
echo "registration_mode_changed=yes"
echo "environment_backup=${env_backup}"
