#!/bin/bash
# Quick start guide for Inbox Bridge with Gmail 2FA support

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     INBOX BRIDGE - Quick Start (Gmail 2FA Support)         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check virtual environment
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import google_auth_oauthlib" 2>/dev/null; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -q -r requirements.txt
fi

echo -e "${GREEN}✓ Environment ready${NC}\n"

# Check configuration
if [ ! -f ".env" ]; then
    echo -e "${RED}✗ .env file not found${NC}"
    echo "Create .env with your Telegram bot token and chat ID"
    echo "See SETUP.md section 3 for instructions"
    exit 1
fi

if [ ! -f "config/accounts.json" ]; then
    echo -e "${RED}✗ config/accounts.json not found${NC}"
    echo "Create config/accounts.json with your email accounts"
    echo "See SETUP.md section 4 for instructions"
    exit 1
fi

echo "Configuration found ✓"
echo ""

# Show menu
echo -e "${BLUE}What would you like to do?${NC}\n"
echo "  1. Test email accounts (check authentication)"
echo "  2. Setup Gmail OAuth2 (for 2FA accounts)"
echo "  3. Start monitoring (background service)"
echo "  4. Show logs"
echo "  5. View documentation"
echo ""

read -p "Enter option (1-5): " choice

case $choice in
    1)
        echo ""
        echo -e "${BLUE}Testing accounts...${NC}\n"
        python test_accounts.py
        ;;
    2)
        echo ""
        echo -e "${BLUE}Starting OAuth2 setup...${NC}\n"
        echo "Before continuing, ensure you have:"
        echo "  1. Google OAuth2 credentials (client_id and client_secret)"
        echo "  2. Added GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET to .env"
        echo ""
        read -p "Continue? (y/n): " confirm
        if [ "$confirm" = "y" ]; then
            python auth_setup.py
        fi
        ;;
    3)
        echo ""
        echo -e "${BLUE}Starting Inbox Bridge...${NC}\n"
        python run.py
        ;;
    4)
        if [ -f "logs/email_monitor.log" ]; then
            echo ""
            echo -e "${BLUE}Recent logs:${NC}\n"
            tail -50 logs/email_monitor.log
        else
            echo "No logs found yet"
        fi
        ;;
    5)
        echo ""
        echo -e "${BLUE}Available documentation:${NC}\n"
        echo "  • SETUP.md - Complete setup guide"
        echo "  • OAUTH2_README.md - OAuth2 configuration details"
        echo "  • QUICK_START.md - Spanish quick start"
        echo ""
        read -p "Open which file? (setup/oauth2/quick/none): " doc
        case $doc in
            setup) cat SETUP.md | less ;;
            oauth2) cat OAUTH2_README.md | less ;;
            quick) cat QUICK_START.md | less ;;
            *) echo "No file opened" ;;
        esac
        ;;
    *)
        echo -e "${RED}Invalid option${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}Done!${NC}"
echo ""
