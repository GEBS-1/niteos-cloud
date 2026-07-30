#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/niteos-cloud}"
SERVICE_NAME="${SERVICE_NAME:-niteos-cloud}"
APP_PORT="${NITEOS_PORT:-8080}"
BACKUP_DIR="${BACKUP_DIR:-/opt/backups}"

echo "Deploying NITEOS Cloud to ${APP_DIR}"

sudo mkdir -p "$BACKUP_DIR"

if [ -d "$APP_DIR" ]; then
  backup="$BACKUP_DIR/niteos-cloud-$(date +%Y%m%d-%H%M%S).tar.gz"
  echo "Existing app found. Backup: $backup"
  sudo tar -czf "$backup" -C "$(dirname "$APP_DIR")" "$(basename "$APP_DIR")"
fi

sudo mkdir -p "$APP_DIR"
sudo rsync -a --delete \
  --exclude ".git" \
  --exclude ".venv" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  --exclude "routerai_api_key.txt" \
  --exclude "gemini_api_key.txt" \
  ./ "$APP_DIR"/

cd "$APP_DIR"

if [ ! -f ".env" ]; then
  if [ -z "${ROUTERAI_API_KEY:-}" ]; then
    echo "ERROR: ROUTERAI_API_KEY is not set and ${APP_DIR}/.env does not exist."
    echo "Create .env or run: ROUTERAI_API_KEY=... sudo -E bash deploy_ubuntu.sh"
    exit 1
  fi
  sudo tee .env >/dev/null <<EOF
ROUTERAI_API_KEY=${ROUTERAI_API_KEY}
ROUTERAI_IMAGE_MODEL=${ROUTERAI_IMAGE_MODEL:-google/gemini-2.5-flash-image}
NITEOS_HOST=127.0.0.1
NITEOS_PORT=${APP_PORT}
EOF
  sudo chmod 600 .env
fi

sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip nginx rsync

sudo python3 -m venv "$APP_DIR/.venv"
sudo "$APP_DIR/.venv/bin/pip" install --upgrade pip
sudo "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements_cloud.txt"

sudo chown -R www-data:www-data "$APP_DIR"

sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" >/dev/null <<EOF
[Unit]
Description=NITEOS Concept Light Cloud
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/uvicorn cloud_app:app --host 127.0.0.1 --port ${APP_PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

sudo tee "/etc/nginx/sites-available/${SERVICE_NAME}" >/dev/null <<EOF
server {
    listen 80;
    server_name _;

    client_max_body_size 50m;

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

sudo ln -sf "/etc/nginx/sites-available/${SERVICE_NAME}" "/etc/nginx/sites-enabled/${SERVICE_NAME}"
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

echo "Done."
echo "Open: http://$(hostname -I | awk '{print $1}')/"
sudo systemctl --no-pager --full status "$SERVICE_NAME" || true
