#!/usr/bin/env bash

# Inbox Bridge — Service Installation Script
# This script installs Inbox Bridge as a systemd service that runs automatically
# at startup and restarts if it crashes.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${CYAN}${BOLD}"
echo "  ╔════════════════════════════════════════════════╗"
echo "  ║   📬  INBOX BRIDGE — SERVICE INSTALLER  📬     ║"
echo "  ╚════════════════════════════════════════════════╝"
echo -e "${NC}\n"

# Check if running as root (required for systemd)
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}ERROR: This script must be run with sudo${NC}"
    echo "Run: sudo bash install-service.sh"
    exit 1
fi

# Get the current user (the one who ran sudo)
CURRENT_USER="${SUDO_USER:-$USER}"

if [ -z "$CURRENT_USER" ] || [ "$CURRENT_USER" = "root" ]; then
    echo -e "${RED}ERROR: Could not determine the current user${NC}"
    exit 1
fi

echo -e "${YELLOW}Installing Inbox Bridge as a system service for user: ${BOLD}${CURRENT_USER}${NC}\n"

# Get the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Project directory: $PROJECT_DIR"
echo ""

# Check if .env exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${RED}ERROR: .env file not found at $PROJECT_DIR/.env${NC}"
    echo "Please configure the .env file first (see SETUP.md)"
    exit 1
fi

# Check if accounts.json exists
if [ ! -f "$PROJECT_DIR/config/accounts.json" ]; then
    echo -e "${RED}ERROR: config/accounts.json not found${NC}"
    echo "Please configure your email accounts first (see SETUP.md)"
    exit 1
fi

# Check if venv exists
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo -e "${RED}ERROR: Virtual environment not found${NC}"
    echo "Run ./start.sh first to set up the environment"
    exit 1
fi

echo -e "${GREEN}✔ All configuration files found${NC}\n"

# Create the systemd service file
SERVICE_FILE="/etc/systemd/system/inbox-bridge-${CURRENT_USER}.service"

echo -e "${YELLOW}Creating systemd service file...${NC}"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Inbox Bridge — Email Monitor Bot Service
Documentation=https://github.com/SantiCode17/multi-account-mail-bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${CURRENT_USER}
Group=${CURRENT_USER}
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${PROJECT_DIR}/venv/bin:/usr/local/bin:/usr/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=${PROJECT_DIR}/venv/bin/python ${PROJECT_DIR}/run.py

# Restart policy — always come back after failures
Restart=always
RestartSec=10
StartLimitIntervalSec=300
StartLimitBurst=5

# Graceful shutdown
KillSignal=SIGTERM
TimeoutStopSec=30

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=inbox-bridge

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✔ Service file created at $SERVICE_FILE${NC}\n"

# Reload systemd daemon
echo -e "${YELLOW}Reloading systemd daemon...${NC}"
systemctl daemon-reload
echo -e "${GREEN}✔ Daemon reloaded${NC}\n"

# Enable the service
echo -e "${YELLOW}Enabling service to start at boot...${NC}"
systemctl enable "inbox-bridge-${CURRENT_USER}.service"
echo -e "${GREEN}✔ Service enabled${NC}\n"

# Start the service
echo -e "${YELLOW}Starting the service...${NC}"
systemctl start "inbox-bridge-${CURRENT_USER}.service"
sleep 2
echo -e "${GREEN}✔ Service started${NC}\n"

# Check status
echo -e "${CYAN}${BOLD}Service Status:${NC}"
systemctl status "inbox-bridge-${CURRENT_USER}.service" || true

echo ""
echo -e "${GREEN}${BOLD}✓ Installation complete!${NC}\n"

echo -e "${CYAN}Useful commands:${NC}"
echo "  Check status:     systemctl status inbox-bridge-${CURRENT_USER}.service"
echo "  View logs:        journalctl -u inbox-bridge-${CURRENT_USER}.service -f"
echo "  Stop service:     systemctl stop inbox-bridge-${CURRENT_USER}.service"
echo "  Start service:    systemctl start inbox-bridge-${CURRENT_USER}.service"
echo "  Uninstall:        sudo systemctl disable inbox-bridge-${CURRENT_USER}.service && sudo rm $SERVICE_FILE && sudo systemctl daemon-reload"
echo ""
                    