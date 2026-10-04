#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "请使用 sudo 运行本脚本。" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
DOCKER_BIN="$(command -v docker || true)"
if [[ -z "$DOCKER_BIN" ]]; then
  echo "未找到 docker，无法安装学校请假定时任务。" >&2
  exit 1
fi

CUTOFF="${LEAVE_DAILY_CUTOFF:-}"
if [[ -z "$CUTOFF" && -f "$ENV_FILE" ]]; then
  CUTOFF="$(sed -n 's/^LEAVE_DAILY_CUTOFF=//p' "$ENV_FILE" | tail -n 1 | tr -d '\r')"
fi
CUTOFF="${CUTOFF:-11:30}"
if [[ ! "$CUTOFF" =~ ^([01][0-9]|2[0-3]):[0-5][0-9]$ ]]; then
  echo "LEAVE_DAILY_CUTOFF 必须使用 HH:MM 24 小时格式，当前值：$CUTOFF" >&2
  exit 1
fi

SERVICE_PATH="/etc/systemd/system/tarsgo-school-leave.service"
TIMER_PATH="/etc/systemd/system/tarsgo-school-leave.timer"

cat > "$SERVICE_PATH" <<EOF
[Unit]
Description=TARS Base school leave collection
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=$ROOT_DIR
ExecStart=$DOCKER_BIN compose exec -T api python -m app.jobs.collect_school_leave
EOF

cat > "$TIMER_PATH" <<EOF
[Unit]
Description=Collect TARS Base school leave requests daily

[Timer]
OnCalendar=*-*-* $CUTOFF:00 Asia/Shanghai
Persistent=true
AccuracySec=1min
Unit=tarsgo-school-leave.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now tarsgo-school-leave.timer
systemctl list-timers tarsgo-school-leave.timer --no-pager
