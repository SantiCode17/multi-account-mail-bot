#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  Inbox Bridge — Management CLI
#  Usage: ./ctl.sh {start|stop|restart|status|logs|health|build|destroy}
# ══════════════════════════════════════════════════════════════════
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE_FILE="docker-compose.yml"
SERVICE_NAME="inbox-bridge"
HEALTH_URL="http://127.0.0.1:8080/health"

# ── Colors ──────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ── Helpers ─────────────────────────────────────────────────────

banner() {
    echo ""
    echo -e "${CYAN}${BOLD}"
    echo "  ╔══════════════════════════════════════════╗"
    echo "  ║        📬  INBOX BRIDGE  CTL  📬         ║"
    echo "  ║     Production Management Console        ║"
    echo "  ╚══════════════════════════════════════════╝"
    echo -e "${NC}"
}

info()    { echo -e "${GREEN}[✔]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
error()   { echo -e "${RED}[✖]${NC} $*"; }
section() { echo -e "\n${CYAN}${BOLD}── $* ──${NC}"; }

check_docker() {
    if ! command -v docker &>/dev/null; then
        error "Docker is not installed."
        echo "  Install it from: https://docs.docker.com/get-docker/"
        exit 1
    fi
    if ! docker info &>/dev/null 2>&1; then
        error "Docker daemon is not running."
        echo "  Start Docker Desktop or run: sudo systemctl start docker"
        exit 1
    fi
}

check_env() {
    if [ ! -f ".env" ]; then
        error ".env file not found"
        echo "  Copy the template:  cp .env.example .env"
        echo "  Then edit it with your Telegram credentials."
        exit 1
    fi
}

# ── Commands ────────────────────────────────────────────────────

cmd_build() {
    section "Building image"
    docker compose -f "$COMPOSE_FILE" build --no-cache
    info "Image built successfully"
}

cmd_start() {
    section "Starting Inbox Bridge"
    check_env

    # Build if image doesn't exist
    if ! docker image inspect inbox-bridge:latest &>/dev/null 2>&1; then
        warn "Image not found — building first..."
        docker compose -f "$COMPOSE_FILE" build
    fi

    docker compose -f "$COMPOSE_FILE" up -d
    info "Container started in background"
    echo ""

    # Wait a moment and show health
    echo -e "${DIM}Waiting for health check...${NC}"
    sleep 5
    cmd_health_quiet || true
    echo ""
    echo -e "${GREEN}${BOLD}✓ Inbox Bridge is running in the background.${NC}"
    echo -e "${DIM}  It will restart automatically after crashes or reboots.${NC}"
    echo -e "${DIM}  Use './ctl.sh logs' to follow the output.${NC}"
}

cmd_stop() {
    section "Stopping Inbox Bridge"
    docker compose -f "$COMPOSE_FILE" stop
    info "Container stopped"
    echo -e "${DIM}  The bot will NOT restart until you run './ctl.sh start'.${NC}"
}

cmd_restart() {
    section "Restarting Inbox Bridge"
    docker compose -f "$COMPOSE_FILE" restart
    info "Container restarted"
    sleep 3
    cmd_health_quiet || true
}

cmd_status() {
    section "Container Status"
    local state
    state=$(docker inspect --format='{{.State.Status}}' "$SERVICE_NAME" 2>/dev/null || echo "not found")
    local uptime
    uptime=$(docker inspect --format='{{.State.StartedAt}}' "$SERVICE_NAME" 2>/dev/null || echo "")

    case "$state" in
        running)
            info "Status:  ${GREEN}${BOLD}RUNNING${NC}"
            echo -e "  Started: ${uptime}"
            echo ""
            docker compose -f "$COMPOSE_FILE" ps
            echo ""
            cmd_health_quiet || true
            ;;
        exited)
            local exit_code
            exit_code=$(docker inspect --format='{{.State.ExitCode}}' "$SERVICE_NAME" 2>/dev/null || echo "?")
            error "Status:  ${RED}STOPPED${NC} (exit code: $exit_code)"
            echo ""
            echo "  Last 10 log lines:"
            docker compose -f "$COMPOSE_FILE" logs --tail=10
            ;;
        *)
            warn "Status:  ${YELLOW}$state${NC}"
            ;;
    esac
}

cmd_logs() {
    section "Following logs (Ctrl+C to exit)"
    local lines="${1:-100}"
    docker compose -f "$COMPOSE_FILE" logs -f --tail="$lines"
}

cmd_health() {
    section "Health Check"
    cmd_health_quiet
}

cmd_health_quiet() {
    if command -v curl &>/dev/null; then
        local response
        response=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 "$HEALTH_URL" 2>/dev/null || echo "000")

        if [ "$response" = "200" ]; then
            info "Health: ${GREEN}${BOLD}HEALTHY${NC}"
            curl -s "$HEALTH_URL" 2>/dev/null | python3 -m json.tool 2>/dev/null || true
            return 0
        elif [ "$response" = "503" ]; then
            warn "Health: ${YELLOW}UNHEALTHY${NC}"
            curl -s "$HEALTH_URL" 2>/dev/null | python3 -m json.tool 2>/dev/null || true
            return 1
        else
            error "Health: ${RED}UNREACHABLE${NC} (is the container running?)"
            return 1
        fi
    else
        warn "curl not available — skipping health check"
        return 0
    fi
}

cmd_destroy() {
    section "Destroying container and image"
    read -p "Are you sure? This removes the container and image. [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker compose -f "$COMPOSE_FILE" down --rmi local --remove-orphans
        info "Container and image removed"
    else
        warn "Cancelled"
    fi
}

cmd_update() {
    section "Updating Inbox Bridge"
    info "Pulling latest code..."
    git pull origin main 2>/dev/null || warn "git pull failed (not a problem if running locally)"
    info "Rebuilding image..."
    docker compose -f "$COMPOSE_FILE" build
    info "Restarting with new image..."
    docker compose -f "$COMPOSE_FILE" up -d
    sleep 5
    cmd_health_quiet || true
    info "Update complete"
}

# ── Usage ───────────────────────────────────────────────────────

usage() {
    banner
    echo "Usage: ./ctl.sh <command>"
    echo ""
    echo "Commands:"
    echo -e "  ${GREEN}start${NC}     Start the bot in background (survives reboots)"
    echo -e "  ${GREEN}stop${NC}      Stop the bot"
    echo -e "  ${GREEN}restart${NC}   Restart the bot"
    echo -e "  ${GREEN}status${NC}    Show container status and health"
    echo -e "  ${GREEN}logs${NC}      Follow live logs (Ctrl+C to exit)"
    echo -e "  ${GREEN}health${NC}    Check if the bot is healthy"
    echo -e "  ${GREEN}build${NC}     Rebuild the Docker image"
    echo -e "  ${GREEN}update${NC}    Pull latest code, rebuild, and restart"
    echo -e "  ${GREEN}destroy${NC}   Remove container and image"
    echo ""
    echo "Examples:"
    echo "  ./ctl.sh start          # Start and forget"
    echo "  ./ctl.sh logs           # Watch what's happening"
    echo "  ./ctl.sh status         # Quick check"
    echo ""
}

# ── Main ────────────────────────────────────────────────────────

main() {
    check_docker

    case "${1:-}" in
        start)   cmd_start   ;;
        stop)    cmd_stop    ;;
        restart) cmd_restart ;;
        status)  cmd_status  ;;
        logs)    cmd_logs "${2:-100}" ;;
        health)  cmd_health  ;;
        build)   cmd_build   ;;
        update)  cmd_update  ;;
        destroy) cmd_destroy ;;
        *)       usage       ;;
    esac
}

main "$@"
