#!/bin/sh
# Uninstall script for Polyspike Discord Bot
# POSIX-compliant script for safe removal of the bot service

set -e

# Configuration
SERVICE_NAME="polyspike-discord-bot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PROJECT_DIR}/venv"
ENV_FILE="${PROJECT_DIR}/.env"

# Colors for output (POSIX-compliant)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track what was removed for summary
REMOVED_ITEMS=""
SKIPPED_ITEMS=""

# Print colored output
print_info() {
    printf "%b[INFO]%b %s\n" "$GREEN" "$NC" "$1"
}

print_warn() {
    printf "%b[WARN]%b %s\n" "$YELLOW" "$NC" "$1"
}

print_error() {
    printf "%b[ERROR]%b %s\n" "$RED" "$NC" "$1"
}

# Confirm action with user
confirm() {
    prompt="$1"
    default="${2:-n}"
    
    if [ "$default" = "y" ]; then
        prompt_suffix="[Y/n]"
    else
        prompt_suffix="[y/N]"
    fi
    
    printf "%s %s " "$prompt" "$prompt_suffix"
    read -r response
    
    # Handle empty response (use default)
    if [ -z "$response" ]; then
        response="$default"
    fi
    
    case "$response" in
        [yY]|[yY][eE][sS])
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# Check if running as root
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Check if service exists
service_exists() {
    [ -f "$SERVICE_FILE" ]
}

# Check if service is running
service_is_running() {
    systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null
}

# Check if service is enabled
service_is_enabled() {
    systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null
}

# Stop the service
stop_service() {
    if service_is_running; then
        print_info "Stopping ${SERVICE_NAME} service..."
        if systemctl stop "$SERVICE_NAME"; then
            print_info "Service stopped successfully"
            return 0
        else
            print_error "Failed to stop service"
            return 1
        fi
    else
        print_info "Service is not running"
        return 0
    fi
}

# Disable the service
disable_service() {
    if service_is_enabled; then
        print_info "Disabling ${SERVICE_NAME} service..."
        if systemctl disable "$SERVICE_NAME"; then
            print_info "Service disabled successfully"
            return 0
        else
            print_error "Failed to disable service"
            return 1
        fi
    else
        print_info "Service is not enabled"
        return 0
    fi
}

# Remove service file
remove_service_file() {
    if [ -f "$SERVICE_FILE" ]; then
        print_info "Removing service file: ${SERVICE_FILE}"
        if rm -f "$SERVICE_FILE"; then
            print_info "Service file removed successfully"
            REMOVED_ITEMS="${REMOVED_ITEMS}\n  - Service file: ${SERVICE_FILE}"
            return 0
        else
            print_error "Failed to remove service file"
            return 1
        fi
    else
        print_info "Service file does not exist"
        return 0
    fi
}

# Reload systemd daemon
reload_systemd() {
    print_info "Reloading systemd daemon..."
    if systemctl daemon-reload; then
        print_info "Systemd daemon reloaded successfully"
        return 0
    else
        print_error "Failed to reload systemd daemon"
        return 1
    fi
}

# Remove virtual environment
remove_venv() {
    if [ -d "$VENV_DIR" ]; then
        if confirm "Remove virtual environment (${VENV_DIR})?"; then
            print_info "Removing virtual environment..."
            if rm -rf "$VENV_DIR"; then
                print_info "Virtual environment removed successfully"
                REMOVED_ITEMS="${REMOVED_ITEMS}\n  - Virtual environment: ${VENV_DIR}"
                return 0
            else
                print_error "Failed to remove virtual environment"
                return 1
            fi
        else
            print_info "Keeping virtual environment"
            SKIPPED_ITEMS="${SKIPPED_ITEMS}\n  - Virtual environment: ${VENV_DIR}"
            return 0
        fi
    else
        print_info "Virtual environment does not exist"
        return 0
    fi
}

# Remove .env file
remove_env_file() {
    if [ -f "$ENV_FILE" ]; then
        print_warn "The .env file may contain sensitive configuration (API tokens, secrets)"
        if confirm "Remove .env file (${ENV_FILE})?"; then
            print_info "Removing .env file..."
            if rm -f "$ENV_FILE"; then
                print_info ".env file removed successfully"
                REMOVED_ITEMS="${REMOVED_ITEMS}\n  - Environment file: ${ENV_FILE}"
                return 0
            else
                print_error "Failed to remove .env file"
                return 1
            fi
        else
            print_info "Keeping .env file"
            SKIPPED_ITEMS="${SKIPPED_ITEMS}\n  - Environment file: ${ENV_FILE}"
            return 0
        fi
    else
        print_info ".env file does not exist"
        return 0
    fi
}

# Print summary
print_summary() {
    echo ""
    echo "============================================"
    echo "          UNINSTALL SUMMARY"
    echo "============================================"
    
    if [ -n "$REMOVED_ITEMS" ]; then
        echo ""
        printf "%bRemoved:%b" "$GREEN" "$NC"
        printf "%b" "$REMOVED_ITEMS"
        echo ""
    fi
    
    if [ -n "$SKIPPED_ITEMS" ]; then
        echo ""
        printf "%bPreserved:%b" "$YELLOW" "$NC"
        printf "%b" "$SKIPPED_ITEMS"
        echo ""
    fi
    
    echo ""
    echo "============================================"
    
    if [ -z "$REMOVED_ITEMS" ] && [ -z "$SKIPPED_ITEMS" ]; then
        print_info "Nothing was removed - service may not have been installed"
    else
        print_info "Uninstall completed successfully"
    fi
    
    echo ""
    print_info "Note: Project source code remains in ${PROJECT_DIR}"
    print_info "To completely remove the project, manually delete the directory"
}

# Main uninstall function
main() {
    echo "============================================"
    echo "  Polyspike Discord Bot Uninstaller"
    echo "============================================"
    echo ""
    
    check_root
    
    # Check if service is installed
    if ! service_exists; then
        print_warn "Service file not found at ${SERVICE_FILE}"
        print_info "The systemd service may not be installed"
        echo ""
        
        # Still offer to clean up venv and .env
        if [ -d "$VENV_DIR" ] || [ -f "$ENV_FILE" ]; then
            print_info "However, local files were found that can be cleaned up"
            echo ""
        fi
    fi
    
    # Confirmation before proceeding
    echo "This script will:"
    echo "  1. Stop the ${SERVICE_NAME} service (if running)"
    echo "  2. Disable the service from starting at boot"
    echo "  3. Remove the systemd service file"
    echo "  4. Optionally remove the virtual environment"
    echo "  5. Optionally remove the .env configuration file"
    echo ""
    
    if ! confirm "Do you want to proceed with uninstallation?" "n"; then
        print_info "Uninstallation cancelled"
        exit 0
    fi
    
    echo ""
    
    # Stop and disable service
    if service_exists; then
        stop_service
        disable_service
        remove_service_file
        reload_systemd
        REMOVED_ITEMS="${REMOVED_ITEMS}\n  - Systemd service: ${SERVICE_NAME}"
    fi
    
    echo ""
    
    # Optional cleanup
    remove_venv
    echo ""
    remove_env_file
    
    # Print summary
    print_summary
}

# Run main function
main "$@"
