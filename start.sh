#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

print_banner() {
    echo ""
    echo -e "${CYAN}${BOLD}"
    echo "  ╔══════════════════════════════════════════╗"
    echo "  ║        📬  INBOX BRIDGE  📬              ║"
    echo "  ║   Multi-Account Email Monitor Bot        ║"
    echo "  ╚══════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_python() {
    if command -v python3 &>/dev/null; then
        PYTHON=python3
    elif command -v python &>/dev/null; then
        PYTHON=python
    else
        echo -e "${RED}ERROR: Python 3 is not installed.${NC}"
        echo "Install it from https://www.python.org/downloads/"
        exit 1
    fi

    PY_VERSION=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PY_MAJOR=$($PYTHON -c 'import sys; print(sys.version_info.major)')
    PY_MINOR=$($PYTHON -c 'import sys; print(sys.version_info.minor)')

    if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
        echo -e "${RED}ERROR: Python 3.10+ is required (found $PY_VERSION).${NC}"
        exit 1
    fi

    echo -e "${GREEN}✔ Python $PY_VERSION detected${NC}"
}

setup_venv() {
    if [ ! -d "venv" ]; then
        echo -e "${YELLOW}Creating virtual environment...${NC}"
        $PYTHON -m venv venv
        echo -e "${GREEN}✔ Virtual environment created${NC}"
    else
        echo -e "${GREEN}✔ Virtual environment exists${NC}"
    fi

    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    elif [ -f "venv/Scripts/activate" ]; then
        source venv/Scripts/activate
    else
        echo -e "${RED}ERROR: Cannot activate virtual environment.${NC}"
        exit 1
    fi
}

install_deps() {
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
    echo -e "${GREEN}✔ Dependencies installed${NC}"
}

check_env() {
    if [ ! -f ".env" ]; then
        echo ""
        echo -e "${YELLOW}No .env file found. Creating from template...${NC}"
        cp .env.example .env
        echo -e "${RED}${BOLD}"
        echo "  ⚠  IMPORTANT: You must edit the .env file before running!"
        echo ""
        echo "     1. Open .env in a text editor"
        echo "     2. Set your TELEGRAM_BOT_TOKEN"
        echo "     3. Set your TELEGRAM_CHAT_ID"
        echo "     4. Then run this script again"
        echo -e "${NC}"
        exit 1
    fi

    source .env 2>/dev/null || true

    if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ "$TELEGRAM_BOT_TOKEN" = "your_telegram_bot_token_here" ]; then
        echo -e "${RED}ERROR: TELEGRAM_BOT_TOKEN is not configured in .env${NC}"
        exit 1
    fi

    if [ -z "$TELEGRAM_CHAT_ID" ] || [ "$TELEGRAM_CHAT_ID" = "your_telegram_chat_id_here" ]; then
        echo -e "${RED}ERROR: TELEGRAM_CHAT_ID is not configured in .env${NC}"
        exit 1
    fi

    echo -e "${GREEN}✔ Configuration valid${NC}"
}

check_accounts() {
    if [ ! -f "config/accounts.json" ]; then
        echo -e "${RED}ERROR: config/accounts.json not found.${NC}"
        exit 1
    fi

    ACCOUNT_COUNT=$($PYTHON -c "
import json
with open('config/accounts.json') as f:
    data = json.load(f)
print(len(data.get('accounts', [])))
" 2>/dev/null || echo "0")

    echo -e "${GREEN}✔ ${ACCOUNT_COUNT} email account(s) configured${NC}"
}

create_dirs() {
    mkdir -p data logs
    echo -e "${GREEN}✔ Runtime directories ready${NC}"
}

start_monitor() {
    echo ""
    echo -e "${CYAN}${BOLD}Starting Inbox Bridge...${NC}"
    echo -e "${CYAN}Press Ctrl+C to stop${NC}"
    echo ""
    exec python run.py
}

print_banner
check_python
setup_venv
install_deps
check_env
check_accounts
create_dirs
start_monitor
