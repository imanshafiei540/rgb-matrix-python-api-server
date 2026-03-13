#!/bin/bash
set -e

# ============================================================
# RGB Matrix Python API Server - Uninstall
# ============================================================
# Run with: sudo bash uninstall.sh
# ============================================================

APP_NAME="rgb-matrix-server"
INSTALL_DIR="/opt/${APP_NAME}"
SERVICE_FILE="${APP_NAME}.service"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

if [ "$EUID" -ne 0 ]; then
    error "Please run as root: sudo bash uninstall.sh"
fi

info "Uninstalling ${APP_NAME}..."

# Stop and disable service
if systemctl is-active --quiet "${APP_NAME}" 2>/dev/null; then
    info "Stopping service..."
    systemctl stop "${APP_NAME}"
fi

if systemctl is-enabled --quiet "${APP_NAME}" 2>/dev/null; then
    info "Disabling service..."
    systemctl disable "${APP_NAME}"
fi

# Remove service file
if [ -f "/etc/systemd/system/${SERVICE_FILE}" ]; then
    info "Removing service file..."
    rm "/etc/systemd/system/${SERVICE_FILE}"
    systemctl daemon-reload
fi

# Remove application directory
if [ -d "${INSTALL_DIR}" ]; then
    info "Removing ${INSTALL_DIR}..."
    rm -rf "${INSTALL_DIR}"
fi

echo ""
info "${APP_NAME} has been uninstalled."
