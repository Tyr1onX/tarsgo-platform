#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "请使用 sudo 运行本脚本。" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER_BIN="$(command -v docker || true)"
if [[ -z "$DOCKER_BIN" ]]; then
  echo "未找到 docker，无法安装学校请假附件清理任务。" >&2
  exit 1
fi

SERVICE_PATH="/etc/systemd/system/tarsgo-school-leave-result-cleanup.service"
TIMER_PATH="/etc/systemd/system/tarsgo-school-leave-result-cleanup.timer"

cat > "$SERVICE_PATH" <<EOF
[Unit]
Description=TARS Base school leave result cleanup
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=$ROOT_DIR
ExecStart=$DOCKER_BIN compose exec -T api python -m app.jobs.cleanup_school_leave_results
EOF

cat > "$TIMER_PATH" <<EOF
[Unit]
Description=Clean expired TARS Base school leave result files

[Timer]
OnCalendar=hourly
Persistent=true
AccuracySec=1min
Unit=tarsgo-school-leave-result-cleanup.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now tarsgo-school-leave-result-cleanup.timer
systemctl list-timers tarsgo-school-leave-result-cleanup.timer --no-pager
