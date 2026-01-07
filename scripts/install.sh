#!/bin/bash
# Install script for Polyspike Discord Bot
# Robust, idempotent installation script for Raspberry Pi

set -e

# =============================================================================
# Configuration
# =============================================================================

SERVICE_NAME="polyspike-discord-bot"
SERVICE_FILE_SRC="polyspike-discord-bot.service"
SERVICE_FILE_DEST="/etc/systemd/system/${SERVICE_NAME}.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PROJECT_DIR}/venv"
ENV_FILE="${PROJECT_DIR}/.env"
ENV_EXAMPLE="${PROJECT_DIR}/.env.example"
REQUIREMENTS_FILE="${PROJECT_DIR}/requirements.txt"
MIN_PYTHON_VERSION="3.11"

# =============================================================================
# Colors for output
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# =============================================================================
# Output functions
# =============================================================================

print_header() {
    echo ""
    printf "%b%s%b\n" "$BOLD$CYAN" "$1" "$NC"
    echo "--------------------------------------------"
}

print_info() {
    printf "%b[INFO]%b %s\n" "$GREEN" "$NC" "$1"
}

print_warn() {
    printf "%b[WARN]%b %s\n" "$YELLOW" "$NC" "$1"
}

print_error() {
    printf "%b[ERROR]%b %s\n" "$RED" "$NC" "$1"
}

print_step() {
    printf "%b[STEP]%b %s\n" "$BLUE" "$NC" "$1"
}

print_success() {
    printf "%b[OK]%b %s\n" "$GREEN" "$NC" "$1"
}

# =============================================================================
# Help function
# =============================================================================

show_help() {
    printf "%bPolyspike Discord Bot - Installation Script%b\n" "$BOLD" "$NC"
    echo ""
    printf "%bUSAGE:%b\n" "$BOLD" "$NC"
    echo "    ./install.sh [OPTIONS]"
    echo ""
    printf "%bOPTIONS:%b\n" "$BOLD" "$NC"
    echo "    -h, --help          Show this help message and exit"
    echo "    -s, --skip-service  Skip systemd service installation"
    echo "    -y, --yes           Automatic yes to prompts (non-interactive mode)"
    echo "    -v, --verbose       Enable verbose output"
    echo ""
    printf "%bDESCRIPTION:%b\n" "$BOLD" "$NC"
    echo "    This script sets up the Polyspike Discord Bot on a Raspberry Pi or"
    echo "    Linux system. It performs the following steps:"
    echo ""
    echo "    1. Pre-flight checks (Linux, Python 3.11+, Mosquitto)"
    echo "    2. Creates Python virtual environment"
    echo "    3. Installs Python dependencies"
    echo "    4. Creates .env configuration file from template"
    echo "    5. Optionally installs systemd service for auto-start"
    echo ""
    printf "%bREQUIREMENTS:%b\n" "$BOLD" "$NC"
    echo "    - Linux operating system (Raspberry Pi recommended)"
    echo "    - Python ${MIN_PYTHON_VERSION} or higher"
    echo "    - Mosquitto MQTT broker installed and running"
    echo "    - sudo access (for systemd service installation only)"
    echo ""
    printf "%bEXAMPLES:%b\n" "$BOLD" "$NC"
    echo "    # Standard installation with prompts"
    echo "    ./install.sh"
    echo ""
    echo "    # Skip service installation"
    echo "    ./install.sh --skip-service"
    echo ""
    echo "    # Non-interactive installation"
    echo "    ./install.sh --yes"
    echo ""
    printf "%bPOST-INSTALLATION:%b\n" "$BOLD" "$NC"
    echo "    1. Edit .env file with your Discord and MQTT credentials"
    echo "    2. Start the service: sudo systemctl start ${SERVICE_NAME}"
    echo "    3. Check status: sudo systemctl status ${SERVICE_NAME}"
    echo "    4. View logs: sudo journalctl -u ${SERVICE_NAME} -f"
    echo ""
}

# =============================================================================
# Utility functions
# =============================================================================

# Confirm action with user
confirm() {
    local prompt="$1"
    local default="${2:-n}"

    # Auto-confirm in non-interactive mode
    if [[ "$AUTO_YES" == "true" ]]; then
        return 0
    fi

    local prompt_suffix
    if [[ "$default" == "y" ]]; then
        prompt_suffix="[Y/n]"
    else
        prompt_suffix="[y/N]"
    fi

    printf "%s %s " "$prompt" "$prompt_suffix"
    read -r response

    # Handle empty response (use default)
    if [[ -z "$response" ]]; then
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

# Compare version numbers
version_ge() {
    # Returns 0 (true) if $1 >= $2
    printf '%s\n%s\n' "$2" "$1" | sort -V -C
}

# Get Python version as comparable string
get_python_version() {
    local python_cmd="$1"
    "$python_cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null
}

# =============================================================================
# Pre-flight checks
# =============================================================================

check_linux() {
    print_step "Checking operating system..."
    
    if [[ "$(uname -s)" != "Linux" ]]; then
        print_error "This script is designed for Linux systems only"
        print_error "Detected OS: $(uname -s)"
        exit 1
    fi
    
    # Check if running on Raspberry Pi (optional info)
    if [[ -f /proc/device-tree/model ]]; then
        local model
        model=$(tr -d '\0' < /proc/device-tree/model)
        if [[ "$model" == *"Raspberry Pi"* ]]; then
            print_success "Running on: $model"
        else
            print_info "Running on Linux: $model"
        fi
    else
        print_success "Running on Linux"
    fi
}

check_not_root() {
    print_step "Checking user permissions..."
    
    if [[ "$(id -u)" -eq 0 ]]; then
        print_error "Do not run this script as root"
        print_error "Run as a regular user; sudo will be requested when needed"
        exit 1
    fi
    
    print_success "Running as user: $(whoami)"
}

check_python() {
    print_step "Checking Python version..."
    
    local python_cmd=""
    local python_version=""
    
    # Try different Python commands in order of preference
    for cmd in python3.12 python3.11 python3 python; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$(get_python_version "$cmd")
            if [[ -n "$ver" ]] && version_ge "$ver" "$MIN_PYTHON_VERSION"; then
                python_cmd="$cmd"
                python_version="$ver"
                break
            fi
        fi
    done
    
    if [[ -z "$python_cmd" ]]; then
        print_error "Python ${MIN_PYTHON_VERSION}+ is required but not found"
        print_error "Please install Python ${MIN_PYTHON_VERSION} or higher"
        print_info "On Raspberry Pi: sudo apt update && sudo apt install python3"
        exit 1
    fi
    
    PYTHON_CMD="$python_cmd"
    print_success "Found Python $python_version ($python_cmd)"
}

check_mosquitto() {
    print_step "Checking Mosquitto MQTT broker..."
    
    # Check if mosquitto is installed
    if ! command -v mosquitto &>/dev/null; then
        print_warn "Mosquitto does not appear to be installed"
        print_info "Install with: sudo apt update && sudo apt install mosquitto mosquitto-clients"
        
        if ! confirm "Continue anyway?"; then
            exit 1
        fi
        return
    fi
    
    # Check if mosquitto service is running
    if systemctl is-active --quiet mosquitto 2>/dev/null; then
        print_success "Mosquitto is installed and running"
    else
        print_warn "Mosquitto is installed but not running"
        print_info "Start with: sudo systemctl start mosquitto"
        print_info "Enable at boot: sudo systemctl enable mosquitto"
        
        if ! confirm "Continue anyway?"; then
            exit 1
        fi
    fi
}

check_project_files() {
    print_step "Checking project files..."
    
    local missing_files=()
    
    if [[ ! -f "$REQUIREMENTS_FILE" ]]; then
        missing_files+=("requirements.txt")
    fi
    
    if [[ ! -f "$ENV_EXAMPLE" ]]; then
        missing_files+=(".env.example")
    fi
    
    if [[ ! -f "${PROJECT_DIR}/${SERVICE_FILE_SRC}" ]]; then
        missing_files+=("$SERVICE_FILE_SRC")
    fi
    
    if [[ ${#missing_files[@]} -gt 0 ]]; then
        print_error "Missing required project files:"
        for file in "${missing_files[@]}"; do
            print_error "  - $file"
        done
        exit 1
    fi
    
    print_success "All required project files present"
}

run_prechecks() {
    print_header "Running Pre-flight Checks"
    
    check_linux
    check_not_root
    check_python
    check_mosquitto
    check_project_files
    
    echo ""
    print_success "All pre-flight checks passed!"
}

# =============================================================================
# Installation functions
# =============================================================================

create_venv() {
    print_header "Setting Up Virtual Environment"
    
    if [[ -d "$VENV_DIR" ]]; then
        # Check if venv is valid
        if [[ -f "${VENV_DIR}/bin/activate" ]] && [[ -f "${VENV_DIR}/bin/python" ]]; then
            print_info "Virtual environment already exists at: $VENV_DIR"
            print_success "Reusing existing virtual environment"
            return 0
        else
            print_warn "Invalid virtual environment found, recreating..."
            rm -rf "$VENV_DIR"
        fi
    fi
    
    print_step "Creating virtual environment..."
    
    if "$PYTHON_CMD" -m venv "$VENV_DIR"; then
        print_success "Virtual environment created at: $VENV_DIR"
    else
        print_error "Failed to create virtual environment"
        print_info "Try: sudo apt install python3-venv"
        exit 1
    fi
}

install_requirements() {
    print_header "Installing Python Dependencies"
    
    print_step "Upgrading pip..."
    "${VENV_DIR}/bin/python" -m pip install --upgrade pip --quiet
    
    print_step "Installing requirements from requirements.txt..."
    
    if "${VENV_DIR}/bin/pip" install -r "$REQUIREMENTS_FILE" --quiet; then
        print_success "Dependencies installed successfully"
    else
        print_error "Failed to install dependencies"
        exit 1
    fi
    
    # Show installed packages in verbose mode
    if [[ "$VERBOSE" == "true" ]]; then
        echo ""
        print_info "Installed packages:"
        "${VENV_DIR}/bin/pip" list
    fi
}

setup_env_file() {
    print_header "Setting Up Configuration"
    
    if [[ -f "$ENV_FILE" ]]; then
        print_info ".env file already exists at: $ENV_FILE"
        print_success "Keeping existing configuration"
        return 0
    fi
    
    print_step "Creating .env from template..."
    
    if cp "$ENV_EXAMPLE" "$ENV_FILE"; then
        # Set restrictive permissions on .env (contains secrets)
        chmod 600 "$ENV_FILE"
        print_success ".env file created at: $ENV_FILE"
        echo ""
        print_warn "IMPORTANT: You must edit .env with your credentials!"
        print_info "Required settings:"
        print_info "  - DISCORD_BOT_TOKEN: Your Discord bot token"
        print_info "  - DISCORD_GUILD_ID: Your Discord server ID"
        print_info "  - DISCORD_CHANNEL_ID: Channel for notifications"
        echo ""
        print_info "Edit with: nano ${ENV_FILE}"
    else
        print_error "Failed to create .env file"
        exit 1
    fi
}

install_systemd_service() {
    print_header "Systemd Service Installation"
    
    if [[ "$SKIP_SERVICE" == "true" ]]; then
        print_info "Skipping service installation (--skip-service flag)"
        return 0
    fi
    
    # Check if service already exists and is identical
    if [[ -f "$SERVICE_FILE_DEST" ]]; then
        print_info "Service file already exists at: $SERVICE_FILE_DEST"
        
        # Generate expected service content
        local expected_content
        expected_content=$(generate_service_file)
        local current_content
        current_content=$(cat "$SERVICE_FILE_DEST")
        
        if [[ "$expected_content" == "$current_content" ]]; then
            print_success "Service file is up to date"
            return 0
        else
            print_warn "Service file differs from expected configuration"
            if ! confirm "Update the service file?"; then
                print_info "Keeping existing service file"
                return 0
            fi
        fi
    else
        echo "This will install a systemd service that:"
        echo "  - Runs the bot automatically on system boot"
        echo "  - Restarts the bot if it crashes"
        echo "  - Integrates with systemd logging (journalctl)"
        echo ""
        
        if ! confirm "Install systemd service?"; then
            print_info "Skipping service installation"
            return 0
        fi
    fi
    
    # Generate service file with current paths
    print_step "Generating service file..."
    local service_content
    service_content=$(generate_service_file)
    
    # Install service file (requires sudo)
    print_step "Installing service file (requires sudo)..."
    
    if echo "$service_content" | sudo tee "$SERVICE_FILE_DEST" > /dev/null; then
        print_success "Service file installed at: $SERVICE_FILE_DEST"
    else
        print_error "Failed to install service file"
        print_info "You may need to run: sudo cp ${PROJECT_DIR}/${SERVICE_FILE_SRC} ${SERVICE_FILE_DEST}"
        return 1
    fi
    
    # Reload systemd
    print_step "Reloading systemd daemon..."
    if sudo systemctl daemon-reload; then
        print_success "Systemd daemon reloaded"
    else
        print_error "Failed to reload systemd daemon"
        return 1
    fi
    
    # Enable service
    print_step "Enabling service for auto-start..."
    if sudo systemctl enable "$SERVICE_NAME" --quiet; then
        print_success "Service enabled for auto-start"
    else
        print_error "Failed to enable service"
        return 1
    fi
}

generate_service_file() {
    local current_user
    current_user=$(whoami)
    local current_group
    current_group=$(id -gn)
    
    cat << EOF
[Unit]
Description=Polyspike Discord Bot
Documentation=https://github.com/your-org/polyspike-discord-bot
After=network-online.target mosquitto.service
Wants=network-online.target
Requires=mosquitto.service

[Service]
Type=simple
User=${current_user}
Group=${current_group}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_DIR}/bin/python -m src.main

# Restart configuration
Restart=on-failure
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=polyspike-discord-bot

# Environment
Environment=PYTHONUNBUFFERED=1

# Security hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
}

# =============================================================================
# Summary
# =============================================================================

print_summary() {
    print_header "Installation Complete!"
    
    echo ""
    printf "%bInstalled Components:%b\n" "$GREEN" "$NC"
    echo "  - Virtual environment: ${VENV_DIR}"
    echo "  - Configuration file: ${ENV_FILE}"
    
    if [[ -f "$SERVICE_FILE_DEST" ]] && [[ "$SKIP_SERVICE" != "true" ]]; then
        echo "  - Systemd service: ${SERVICE_NAME}"
    fi
    
    echo ""
    printf "%bNext Steps:%b\n" "$YELLOW" "$NC"
    echo ""
    echo "  1. Edit your configuration:"
    printf "     %bnano %s%b\n" "$CYAN" "$ENV_FILE" "$NC"
    echo ""
    echo "  2. Test the bot manually:"
    printf "     %bsource %s/bin/activate%b\n" "$CYAN" "$VENV_DIR" "$NC"
    printf "     %bpython -m src.main%b\n" "$CYAN" "$NC"
    echo ""
    
    if [[ -f "$SERVICE_FILE_DEST" ]]; then
        echo "  3. Start the service:"
        printf "     %bsudo systemctl start %s%b\n" "$CYAN" "$SERVICE_NAME" "$NC"
        echo ""
        echo "  4. Check service status:"
        printf "     %bsudo systemctl status %s%b\n" "$CYAN" "$SERVICE_NAME" "$NC"
        echo ""
        echo "  5. View logs:"
        printf "     %bsudo journalctl -u %s -f%b\n" "$CYAN" "$SERVICE_NAME" "$NC"
    fi
    
    echo ""
    echo "============================================"
}

# =============================================================================
# Main
# =============================================================================

main() {
    # Parse command line arguments
    SKIP_SERVICE="false"
    AUTO_YES="false"
    VERBOSE="false"
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help)
                show_help
                exit 0
                ;;
            -s|--skip-service)
                SKIP_SERVICE="true"
                shift
                ;;
            -y|--yes)
                AUTO_YES="true"
                shift
                ;;
            -v|--verbose)
                VERBOSE="true"
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Print banner
    echo ""
    echo "============================================"
    echo "   Polyspike Discord Bot - Installer"
    echo "============================================"
    echo ""
    print_info "Project directory: ${PROJECT_DIR}"
    
    # Run installation
    run_prechecks
    create_venv
    install_requirements
    setup_env_file
    install_systemd_service
    print_summary
}

# Run main function
main "$@"
