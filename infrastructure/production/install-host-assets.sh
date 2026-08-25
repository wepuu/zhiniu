#!/usr/bin/env bash
set -Eeuo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "run as root on the dedicated Ubuntu host" >&2
  exit 1
fi

repo_dir=${1:-/opt/zhiniu/repo}
[[ $(uname -m) == x86_64 ]] || { echo "expected x86_64" >&2; exit 1; }
grep -q '^VERSION_ID="24.04"' /etc/os-release || { echo "expected Ubuntu 24.04" >&2; exit 1; }
command -v docker >/dev/null || { echo "install Docker Engine first" >&2; exit 1; }
docker compose version >/dev/null
[[ -d ${repo_dir}/.git ]] || { echo "clone the repository at ${repo_dir} first" >&2; exit 1; }

memory_kb=$(awk '/MemTotal:/ { print $2 }' /proc/meminfo)
[[ ${memory_kb} -ge 5767168 ]] || { echo "at least 6GB RAM is required" >&2; exit 1; }
free_kb=$(df -Pk /var/lib/docker | awk 'NR == 2 { print $4 }')
[[ ${free_kb} -ge 15728640 ]] || { echo "at least 15GB Docker disk space must be free" >&2; exit 1; }

apt-get update
apt-get install -y age curl git rsync

if ! id zhaoniu-deploy >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash zhaoniu-deploy
fi
install -d -m 0755 -o root -g root /opt/zhiniu /opt/zhiniu/releases
install -d -m 0700 -o root -g root /etc/zhiniu /var/backups/zhiniu
install -m 0755 "${repo_dir}/infrastructure/production/deploy.sh" /usr/local/sbin/zhaoniu-deploy
install -m 0755 "${repo_dir}/infrastructure/production/backup.sh" /usr/local/sbin/zhaoniu-backup
install -m 0755 "${repo_dir}/infrastructure/production/restore-drill.sh" /usr/local/sbin/zhaoniu-restore-drill
visudo -cf "${repo_dir}/infrastructure/production/sudoers-zhaoniu-deploy"
install -m 0440 "${repo_dir}/infrastructure/production/sudoers-zhaoniu-deploy" /etc/sudoers.d/zhaoniu-deploy
install -m 0644 "${repo_dir}/infrastructure/production/systemd/zhaoniu-backup.service" /etc/systemd/system/
install -m 0644 "${repo_dir}/infrastructure/production/systemd/zhaoniu-backup.timer" /etc/systemd/system/

swap_kb=$(awk '/SwapTotal:/ { print $2 }' /proc/meminfo)
if [[ ${swap_kb} -lt 4194304 ]]; then
  [[ ! -e /swapfile ]] || { echo "existing /swapfile is smaller than 4GB; resize it manually" >&2; exit 1; }
  fallocate -l 4G /swapfile
  chmod 0600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >>/etc/fstab
fi
printf 'vm.swappiness=10\n' >/etc/sysctl.d/90-zhaoniu.conf
sysctl --system >/dev/null
systemctl daemon-reload

echo "Host assets installed. Configure /etc/zhiniu/*.env before enabling the backup timer."
